import json
import shutil
import sqlite3
from contextlib import asynccontextmanager, closing
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.api import stations
from app.core.config import Settings
from app.core.public import ReadCache
from app.db.models import Observation
from app.db.session import build_engine
from app.integrations.ambient_weather.parser import parse_report
from app.main import create_app
from app.repositories.ingestion import save_report
from conftest import migrate
from scripts.backup_sqlite import restore_test, run_backup


@pytest.fixture
def settings(database_url, tmp_path):
    return Settings(_env_file=None, database_url=database_url, ingest_networks=["127.0.0.1/32"],
                    allow_simulated=True, max_csv_rows=1, max_page_size=2, backup_dir=tmp_path / "primary",
                    backup_secondary_dir=tmp_path / "secondary", station_delay_seconds=120,
                    station_timeout_seconds=300, public_requests_per_minute=120)


@asynccontextmanager
async def service(settings, role):
    app = create_app(settings, role=role)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://localhost") as api:
            yield api


@pytest.mark.anyio
async def test_roles_and_recovery(settings, payload):
    # Start the reader before any writer or database exists.
    async with service(settings, "public") as reader:
        failure = await reader.get("/api/v1/stations")
        assert failure.status_code == 503 and list(failure.json()) == ["detail"]
        async with service(settings, "ingest") as unavailable:
            assert (await unavailable.get("/health")).status_code == 200
            assert (await unavailable.get("/ready")).status_code == 503
            assert (await unavailable.get("/data/report/", params=payload)).status_code == 503
            migrate(settings.database_url)
            assert (await unavailable.get("/ready")).status_code == 200
        for path in ("/data/report", "/data/report/", "/monitor/stations", "/health", "/ready", "/docs",
                     "/docs-assets/swagger-ui.css", "/redoc", "/openapi.json", "/admin"):
            assert (await reader.get(path)).status_code == 404
        assert (await reader.get("/api/v1/stations")).json() == []
        async with service(settings, "ingest") as writer:
            assert (await writer.get("/api/v1/stations")).status_code == 404
            assert (await writer.get("/ready")).status_code == 200
            sim = {**payload, "dev_simulated": "1"}
            assert (await writer.get("/data/report/", params=sim)).text == "OK"
            assert (await writer.get("/monitor/stations")).json()[0]["communication"] == "online"
        for method in ("POST", "PUT", "PATCH", "DELETE"):
            assert (await reader.request(method, "/api/v1/stations/1")).status_code == 405
        station = (await reader.get("/api/v1/stations/1")).json()
        assert "mac_address" not in station and payload["MAC"] not in json.dumps(station)
        assert station["communication"] == "online" and station["is_simulated"]
    async with service(settings, "public") as restarted:
        observation = (await restarted.get("/api/v1/stations/1/latest")).json()
        assert observation["outdoor_temperature_c"] == 30 and "raw_payload" not in observation


@pytest.mark.anyio
async def test_cache_limits_and_late_arrival(settings, payload, monkeypatch):
    migrate(settings.database_url)
    calls = 0
    original = stations.repo.summary

    def count_queries(*args):
        nonlocal calls
        calls += 1
        return original(*args)

    monkeypatch.setattr(stations.repo, "summary", count_queries)
    base = "/api/v1/stations/1/"
    period = {"start": "2026-11-19T00:00:00Z", "end": "2026-11-21T00:00:00Z"}
    async with service(settings, "public") as reader, service(settings, "ingest") as writer:
        await writer.get("/data/report/", params=payload)
        for _ in range(2):
            assert (await reader.get(base + "summary", params=period)).json()["sample_count"] == 1
        assert calls == 1
        assert (await reader.get(base + "export.csv", params=period)).status_code == 200
        await writer.get("/data/report/", params={**payload, "dateutc": "2026-11-19 16:00:00", "tempf": "32"})
        assert (await reader.get(base + "summary", params=period)).json()["sample_count"] == 2
        assert calls == 2
        assert (await reader.get(base + "latest")).json()["outdoor_temperature_c"] == 0
        assert (await reader.get(base + "export.csv", params=period)).status_code == 422
        assert (await reader.get(base + "observations", params={**period, "page_size": 3})).status_code == 422
        for suffix in ("observations", "summary", "export.csv"):
            assert (await reader.get(base + suffix, params={**period, "start": "2020-01-01T00:00:00Z"})).status_code == 422
        page = (await reader.get(base + "observations", params={**period, "page": 2, "page_size": 1})).json()
        assert len(page["items"]) == 1 and page["items"][0]["outdoor_temperature_c"] == 30


@pytest.mark.anyio
async def test_rate_budget(settings):
    migrate(settings.database_url)
    settings.public_requests_per_minute = 1
    settings.cors_origins = ["https://clima.example.org"]
    async with service(settings, "public") as reader:
        assert (await reader.get("/api/v1/stations")).status_code == 200
        limited = await reader.get("/api/v1/stations", headers={
            "X-Forwarded-For": "203.0.113.10", "Origin": "https://clima.example.org",
        })
        assert limited.status_code == 429 and "Retry-After" in limited.headers
        assert limited.headers["access-control-allow-origin"] == "https://clima.example.org"


@pytest.mark.anyio
async def test_contact_independent_of_measurement(settings, payload):
    migrate(settings.database_url)
    engine = build_engine(settings.database_url)
    try:
        with Session(engine) as db, db.begin():
            for i, seconds in enumerate((60, 180, 900)):
                pairs = {**payload, "MAC": f"02000000000{i}", "dateutc": "2001-01-01 00:00:00", "humidity": "0"}
                save_report(db, parse_report(list(pairs.items())), datetime.now(UTC) - timedelta(seconds=seconds))
        async with service(settings, "public") as reader:
            page = (await reader.get("/api/v1/stations")).json()
            assert [s["communication"] for s in page] == ["online", "delayed"]
            station = (await reader.get("/api/v1/stations/3")).json()
            assert station["communication"] == "offline" and station["seconds_since_measurement"] > 900
    finally:
        engine.dispose()


def test_wal_indexes_upgrade_and_backup(settings, payload, tmp_path):
    cfg = Config("alembic.ini")
    cfg.attributes["database_url"] = settings.database_url
    command.upgrade(cfg, "0001_weather")
    writer = build_engine(settings.database_url, busy_timeout_ms=4321)
    reader = build_engine(settings.database_url, read_only=True)
    report = parse_report(list(payload.items()))
    try:
        with Session(writer) as db, db.begin():
            save_report(db, report, report.measured_at_utc)
        command.upgrade(cfg, "head")
        indexes = inspect(writer).get_indexes("observations")
        assert any(i["column_names"] == ["measured_at_utc"] for i in indexes)
        assert any(i["column_names"][:2] == ["station_id", "received_at_utc"] for i in indexes)
        assert inspect(writer).get_unique_constraints("observations")[0]["column_names"] == ["station_id", "measured_at_utc"]
        with writer.connect() as conn:
            for pragma, expected in [("journal_mode", "wal"), ("busy_timeout", 4321), ("foreign_keys", 1)]:
                assert conn.exec_driver_sql(f"PRAGMA {pragma}").scalar() == expected
        settings.backup_secondary_dir.mkdir()
        with Session(writer) as db, db.begin():
            later = report.model_copy(update={"measured_at_utc": datetime.now(UTC)})
            save_report(db, later, later.measured_at_utc)
            with Session(reader) as view:
                assert len(view.scalars(select(Observation.id)).all()) == 1
            # Back up a live WAL database while a second observation is uncommitted.
            saved = run_backup(settings)
        with Session(reader) as view:
            assert len(view.scalars(select(Observation.id)).all()) == 2
        with pytest.raises(OperationalError), reader.begin() as conn:
            conn.exec_driver_sql("UPDATE stations SET name='Teste' WHERE id=1")
        assert restore_test(saved) == {"stations": 1, "observations": 1}
        assert (settings.backup_secondary_dir / saved.name).read_bytes() == saved.read_bytes()
        with closing(sqlite3.connect(saved)) as conn:
            assert json.loads(conn.execute("SELECT raw_payload FROM observations").fetchone()[0]) == payload
        old = settings.backup_dir / "ws2000-20000101T010203000000Z.sqlite3"
        shutil.copyfile(saved, old)
        unrelated = settings.backup_dir / "arquivo-manual.sqlite3"
        unrelated.touch()
        assert run_backup(settings).is_file()
        assert not old.exists() and unrelated.exists()
    finally:
        reader.dispose()
        writer.dispose()


def test_backup_keeps_local_snapshot_if_secondary_is_unavailable(settings):
    migrate(settings.database_url)
    with pytest.raises(FileNotFoundError):
        run_backup(settings)
    saved, = settings.backup_dir.glob("ws2000-*.sqlite3")
    assert restore_test(saved) == {"stations": 0, "observations": 0}


def test_empty_cache_expiry_and_disabled_cache(monkeypatch):
    cache = ReadCache()
    tick = 10
    monkeypatch.setattr("app.core.public.monotonic", lambda: tick)
    loads = iter(range(10))
    assert cache.get("test", 60, loads.__next__) == 0
    assert cache.get("test", 60, loads.__next__) == 0
    tick += 60
    assert cache.get("test", 60, loads.__next__) == 1
    assert cache.get("test", 0, loads.__next__) == 2


def test_frontend_schema_contains_only_public_operations(settings):
    schema = create_app(settings, role="public").openapi()
    assert len(schema["paths"]) == 6
    assert all(path.startswith("/api/v1/stations") and set(methods) == {"get"}
               for path, methods in schema["paths"].items())
    assert "mac_address" not in json.dumps(schema) and "raw_payload" not in json.dumps(schema)
    assert schema["components"]["schemas"]["ObservationOut"]["properties"]["wind_speed_ms"]["x-unit"] == "m/s"
