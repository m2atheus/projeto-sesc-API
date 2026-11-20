import csv
from io import StringIO

import pytest

pytestmark = pytest.mark.anyio
BASE = "/api/v1/stations/1"


@pytest.fixture
async def populated(client, payload):
    for day, temp in [(2, "68"), (3, "86"), (1, "32")]:
        params = {**payload, "dateutc": f"2026-11-0{day} 12:00:00", "tempf": temp}
        if day == 2:
            del params["humidity"]
        assert (await client.get("/data/report/", params=params)).status_code == 200
    assert (await client.get("/data/report/", params={**payload, "MAC": "112233445566"})).status_code == 200
    return client


async def test_latest_is_last_received_even_if_measurement_older(populated):
    obs = (await populated.get(BASE + "/latest")).json()
    assert obs["outdoor_temperature_c"] == 0
    assert obs["measured_at_utc"] == "2026-11-01T12:00:00Z"
    assert "raw_payload" not in obs


async def test_history(populated):
    params = {"start": "2026-11-02T09:00:00-03:00", "end": "2026-11-03T12:00:00Z",
              "page_size": 1, "order": "desc"}
    path = BASE + "/observations"
    for page, expected in [(1, [30]), (2, [20]), (3, [])]:
        response = await populated.get(path, params={**params, "page": page})
        assert [o["outdoor_temperature_c"] for o in response.json()["items"]] == expected
    for invalid in [{"page_size": 3}, {"page": 0}, {"end": "2026-01-01"},
                    {**params, "end": "2025-11-03T00:00:00Z"}]:
        assert (await populated.get(path, params=invalid)).status_code == 422


async def test_summary(populated):
    stats = (await populated.get(BASE + "/summary", params={"start": "2026-11-02T12:00:00Z"})).json()
    assert stats["sample_count"] == 2
    assert [stats["temperature_" + key + "_c"] for key in ("min", "avg", "max")] == [20, 25, 30]
    assert stats["humidity_avg_pct"] == 60 and stats["wind_max_ms"] == pytest.approx(5.36448)
    assert stats["latest"]["outdoor_temperature_c"] == 30
    empty = (await populated.get(BASE + "/summary", params={"end": "2020-01-01T00:00:00Z"})).json()
    assert empty["sample_count"] == 0 and empty["temperature_avg_c"] is None and empty["latest"] is None


async def test_csv(populated):
    reply = await populated.get(BASE + "/export.csv", params={"end": "2026-11-02T12:00:00Z"})
    assert reply.status_code == 200 and "text/csv" in reply.headers["content-type"]
    rows = list(csv.DictReader(StringIO(reply.content.decode("utf-8"))))
    assert [float(row["Temperatura externa (°C)"]) for row in rows] == [0, 20]
    assert rows[0]["Medição (UTC)"] == "2026-11-01T12:00:00+00:00"
    assert rows[1]["Umidade externa (%)"] == ""


async def test_service_endpoints(client):
    for suffix in ("", "/latest", "/observations", "/summary", "/export.csv"):
        assert (await client.get(BASE + suffix)).status_code == 404
    for path in ("/health", "/ready", "/docs", "/openapi.json", "/docs-assets/swagger-ui-bundle.js",
                 "/docs-assets/swagger-ui.css"):
        assert (await client.get(path)).status_code == 200


async def test_openapi_units_and_csv_contract(client):
    spec = (await client.get("/openapi.json")).json()
    models = spec["components"]["schemas"]
    units = {
        "°C": ("outdoor_temperature_c", "indoor_temperature_c"),
        "%": ("outdoor_humidity_pct", "indoor_humidity_pct"),
        "m/s": ("wind_speed_ms", "wind_gust_ms"),
        "°": ("wind_direction_deg", "wind_gust_direction_deg"),
        "mm": ("daily_rain_mm", "hourly_rain_mm", "weekly_rain_mm", "monthly_rain_mm", "yearly_rain_mm"),
        "hPa": ("absolute_pressure_hpa", "relative_pressure_hpa"),
        "adimensional": ("uv_index",), "W/m²": ("solar_radiation_wm2",),
    }
    summary_units = {
        "°C": ("temperature_min_c", "temperature_avg_c", "temperature_max_c"),
        "%": ("humidity_min_pct", "humidity_avg_pct", "humidity_max_pct"),
        "m/s": ("wind_avg_ms", "wind_max_ms"),
    }
    for model, expected in [("ObservationOut", units), ("Summary", summary_units)]:
        properties = models[model]["properties"]
        for unit, names in expected.items():
            for name in names:
                assert properties[name]["x-unit"] == unit
                assert f"({unit})" in properties[name]["description"]
    observation = models["ObservationOut"]["properties"]
    for name in ("measured_at_utc", "received_at_utc"):
        assert "UTC" in observation[name]["description"]
    export = spec["paths"]["/api/v1/stations/{station_id}/export.csv"]["get"]["responses"]["200"]
    for names in units.values():
        for name in names:
            assert observation[name]["description"] in export["description"]


async def test_readiness_without_migrations(database_url):
    import httpx
    from app.core.config import Settings
    from app.main import create_app

    app = create_app(Settings(_env_file=None, database_url=database_url))
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://localhost") as api:
            assert (await api.get("/health")).status_code == 200
            assert (await api.get("/ready")).status_code == 503
