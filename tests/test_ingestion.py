import asyncio
import json

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.logging import logger
from app.db.models import Observation, Station

pytestmark = pytest.mark.anyio


async def test_protocol_and_raw_payload(app, client, payload, monkeypatch, caplog):
    app.state.settings.diagnostic_payload = True
    monkeypatch.setattr(logger, "handlers", [caplog.handler])
    payload.update(tempinf="77.2", humidityin="42", winddir="230", windgustdir="360", windgustmph="15",
                   yearlyrainin="2", monthlyrainin="1", weeklyrainin=".5", hourlyrainin="0",
                   baromabsin="29.92", baromrelin="29.97", uv="3", solarradiation="320")
    pairs = [*payload.items(), ("extra", "001"), ("extra", "02 & 03")]
    reply = await client.get("/data/report/", params=pairs)
    assert reply.status_code == 200 and reply.text == "OK"
    stations = (await client.get("/api/v1/stations")).json()
    assert len(stations) == 1 and stations[0]["mac_address"] == payload["MAC"].upper()
    metric_values = {
        "outdoor_temperature_c": 30, "indoor_temperature_c": (77.2 - 32) * 5 / 9,
        "outdoor_humidity_pct": 60, "indoor_humidity_pct": 42,
        "wind_speed_ms": 5.36448, "wind_gust_ms": 6.7056,
        "wind_direction_deg": 230, "wind_gust_direction_deg": 360,
        "daily_rain_mm": 2.54, "hourly_rain_mm": 0, "weekly_rain_mm": 12.7,
        "monthly_rain_mm": 25.4, "yearly_rain_mm": 50.8,
        "absolute_pressure_hpa": 29.92 * 33.8638866667, "relative_pressure_hpa": 29.97 * 33.8638866667,
        "uv_index": 3, "solar_radiation_wm2": 320,
    }
    with Session(app.state.engine) as db:
        obs = db.scalars(select(Observation)).one()
        assert obs.raw_payload == {**payload, "extra": ["001", "02 & 03"]}
        assert obs.measured_at_utc.isoformat() == "2026-11-20T14:30:00+00:00"
        assert {key: getattr(obs, key) for key in metric_values} == pytest.approx(metric_values)

    events = [json.loads(record.getMessage()) for record in caplog.records if record.name == logger.name]
    diagnostic, = [event for event in events if event["event"] == "ingestion_payload"]
    assert diagnostic["fields"] == pytest.approx(metric_values)
    assert "02 & 03" not in caplog.text

    base = "/api/v1/stations/1"
    latest = (await client.get(base + "/latest")).json()
    history = (await client.get(base + "/observations")).json()["items"]
    summary = (await client.get(base + "/summary")).json()
    assert latest.keys() == metric_values.keys() | {"id", "station_id", "measured_at_utc", "received_at_utc"}
    assert {key: latest[key] for key in metric_values} == pytest.approx(metric_values)
    assert history == [latest] and summary["latest"] == latest


async def test_optional_and_unknown(client, payload):
    params = {"MAC": payload["MAC"], "dateutc": payload["dateutc"], "humidity": "0", "tempf": "-40"}
    assert (await client.get("/data/report", params=params)).status_code == 200
    obs = (await client.get("/api/v1/stations/1/latest")).json()
    assert obs["measured_at_utc"].endswith("Z") and obs["received_at_utc"].endswith("Z")
    assert obs["outdoor_humidity_pct"] == 0 and obs["daily_rain_mm"] is None
    assert obs["outdoor_temperature_c"] == -40
    params = {**params, "dateutc": "2026-11-20 14:31:00"}
    del params["humidity"], params["tempf"]
    assert (await client.get("/data/report", params={**params, "soilmoisture1": "10"})).status_code == 200


@pytest.mark.parametrize(("key", "value"), [
    ("MAC", ""), ("MAC", "zz:01:02:03:04:05"), ("dateutc", "2026-02-30 12:00:00"),
    ("winddir", "361"), ("windgustdir", "-1"), ("humidity", "101"), ("humidityin", "-1"),
    ("tempf", ""), ("tempf", "NaN"), ("uv", "oops"), ("baromabsin", "1e308"),
    ("humidity", None), ("dateutc", None), ("MAC", None),
])
async def test_rejected_atomically(client, payload, key, value):
    if value is None and key == "humidity":
        params = list(payload.items()) + [("humidity", "40")]
    else:
        params = {**payload, key: value}
        if value is None:
            del params[key]
    assert (await client.get("/data/report", params=params)).status_code == 422
    assert (await client.get("/api/v1/stations")).json() == []


async def test_concurrent_retries_and_mac_normalization(app, client, payload):
    replies = await asyncio.gather(*(client.get("/data/report", params=payload) for _ in range(8)))
    assert [reply.status_code for reply in replies] == [200] * 8
    changed = {**payload, "MAC": payload["MAC"].replace(":", "-").upper(), "tempf": "32"}
    assert (await client.get("/data/report/", params=changed)).status_code == 200
    with Session(app.state.engine) as db:
        assert db.scalar(select(func.count(Station.id))) == 1
        obs = db.scalars(select(Observation)).one()
        assert obs.outdoor_temperature_c == 30 and obs.raw_payload == payload


async def test_ingestion_limits_and_simulator(client, app, payload):
    assert (await client.post("/data/report/", json=payload)).status_code == 405
    assert (await client.request("GET", "/data/report/", content="body")).status_code == 413
    assert (await client.get("/data/report/", params={"x": "a" * 8192})).status_code == 414
    assert (await client.get("/data/report/", params=[("x", "1")] * 129)).status_code == 413
    params = {**payload, "dev_simulated": "1"}
    assert (await client.get("/data/report/", params=params)).status_code == 422
    app.state.settings.allow_simulated = True
    assert (await client.get("/data/report/", params=params)).status_code == 200
    assert (await client.get("/api/v1/stations/1")).json()["is_simulated"] is True
    assert (await client.get("/data/report/", params=payload)).status_code == 409


async def test_network_policy_only_applies_to_ingestion(app, client, payload):
    transport = httpx.ASGITransport(app=app, client=("203.0.113.8", 8000))
    async with httpx.AsyncClient(transport=transport, base_url="http://localhost") as remote:
        response = await remote.get("/data/report/", params=payload, headers={"X-Forwarded-For": "127.0.0.1"})
        assert response.status_code == 403
        assert (await remote.get("/api/v1/stations")).status_code == 200


@pytest.mark.parametrize("encoded", ["%FF", "%xx"])
async def test_invalid_wire_encoding(client, payload, encoded):
    query = str(httpx.QueryParams(payload))
    reply = await client.get(f"/data/report/?{query}&extra={encoded}")
    assert reply.status_code == 422
    assert (await client.get("/api/v1/stations")).json() == []
