from collections.abc import Iterator
from pathlib import Path

from fastapi import Request
from sqlalchemy import create_engine, event, select
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session

from app.db.models import Observation, Station


def build_engine(database_url: str) -> Engine:
    url = make_url(database_url)
    if url.get_backend_name() != "sqlite":
        return create_engine(url, pool_pre_ping=True, hide_parameters=True)

    if url.database and url.database != ":memory:":
        Path(url.database).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(url, connect_args={"check_same_thread": False, "timeout": 15, "autocommit": False},
                           hide_parameters=True)

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _record):
        connection.autocommit = True
        try:
            connection.execute("PRAGMA foreign_keys=ON").close()
        finally:
            connection.autocommit = False

    return engine


def check_database(db: Session) -> None:
    for table in (Station, Observation):
        db.execute(select(table.id).limit(0))


def get_session(request: Request) -> Iterator[Session]:
    with Session(request.app.state.engine) as session:
        yield session
