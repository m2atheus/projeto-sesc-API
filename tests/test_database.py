import os
from uuid import uuid4

import pytest
from alembic import command
from sqlalchemy import create_engine, func, inspect, select
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema

from app.db.models import Observation, Station
from app.db.session import build_engine
from app.integrations.ambient_weather.parser import parse_report
from app.repositories.ingestion import save_report
from conftest import migrate
from scripts.transfer_history import transfer


def check_transactions(url, payload):
    engine = build_engine(url)
    report = parse_report(list(payload.items()))
    try:
        with Session(engine) as db:
            with pytest.raises(IntegrityError), db.begin():
                save_report(db, report, report.measured_at_utc)
                db.add(Observation(station_id=9999999, measured_at_utc=report.measured_at_utc,
                                   received_at_utc=report.measured_at_utc, raw_payload={}))
            assert db.scalar(select(func.count(Station.id))) == 0
            db.rollback()
            with db.begin():
                assert save_report(db, report, report.measured_at_utc)[1]
                assert not save_report(db, report, report.measured_at_utc)[1]
            assert db.scalars(select(Observation)).one().measured_at_utc == report.measured_at_utc
    finally:
        engine.dispose()


def test_migrations_and_rollback(database_url, payload):
    cfg = migrate(database_url)
    check_transactions(database_url, payload)
    command.check(cfg)
    command.downgrade(cfg, "base")
    engine = build_engine(database_url)
    try:
        assert not inspect(engine).has_table("stations")
    finally:
        engine.dispose()
    command.upgrade(cfg, "head")


@pytest.mark.skipif(not os.getenv("TEST_POSTGRES_URL"), reason="TEST_POSTGRES_URL ausente")
def test_postgresql_in_isolated_schema(payload, database_url):
    base = make_url(os.environ["TEST_POSTGRES_URL"])
    assert base.drivername == "postgresql+psycopg"
    admin = create_engine(base)
    schema = "ws2000_test_" + uuid4().hex
    with admin.begin() as conn:
        conn.execute(CreateSchema(schema))
    try:
        url = base.update_query_dict({"options": f"-csearch_path={schema}"}).render_as_string(hide_password=False)
        migrate(url)
        migrate(database_url)
        check_transactions(database_url, payload)
        assert transfer(database_url, url) == {"stations": 1, "observations": 1}
        with pytest.raises(ValueError, match="vazio"):
            transfer(database_url, url)
        engine = build_engine(url)
        try:
            with Session(engine) as db, db.begin():
                assert db.scalars(select(Observation)).one().raw_payload == payload
                report = parse_report(list(payload.items()))
                assert save_report(db, report, report.measured_at_utc) == (1, False)
                report.mac_address = "02:00:00:00:00:99"
                station_id, created = save_report(db, report, report.measured_at_utc)
                assert station_id > 1 and created
                assert db.scalar(select(func.count(Observation.id))) == 2
        finally:
            engine.dispose()
    finally:
        with admin.begin() as conn:
            conn.execute(DropSchema(schema, cascade=True))
        admin.dispose()
