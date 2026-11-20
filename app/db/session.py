from collections.abc import Iterator
from pathlib import Path
from sqlite3 import OperationalError

from fastapi import Request
from sqlalchemy import create_engine, event, select
from sqlalchemy.engine import Engine, make_url
from sqlalchemy.orm import Session

from app.db.models import Observation, Station


def build_engine(database_url: str, *, busy_timeout_ms: int = 15000, read_only: bool = False,
                 existing_only: bool = False) -> Engine:
    url = make_url(database_url)
    if url.get_backend_name() != "sqlite":
        return create_engine(url, pool_pre_ping=True, hide_parameters=True)

    if url.database and url.database != ":memory:":
        path = Path(url.database)
        if read_only or existing_only:
            mode = "ro" if read_only else "rw"
            url = url.set(database=path.resolve().as_uri()).update_query_dict({"mode": mode, "uri": "true"})
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(url, connect_args={"check_same_thread": False, "timeout": busy_timeout_ms / 1000,
                                              "autocommit": False},
                           hide_parameters=True)

    @event.listens_for(engine, "connect")
    def configure_sqlite(connection, _record):
        connection.autocommit = True
        try:
            connection.execute(f"PRAGMA busy_timeout={int(busy_timeout_ms)}").close()
            if url.database and url.database != ":memory:":
                pragma = "PRAGMA journal_mode" if read_only else "PRAGMA journal_mode=WAL"
                mode = connection.execute(pragma).fetchone()[0]
                if mode != "wal":
                    raise OperationalError("SQLite requer WAL em disco local")
            connection.execute("PRAGMA foreign_keys=ON").close()
            if read_only:
                connection.execute("PRAGMA query_only=ON").close()
        finally:
            connection.autocommit = False

    return engine


def check_database(db: Session) -> None:
    for table in (Station, Observation):
        db.execute(select(table.id).limit(0))


def get_session(request: Request) -> Iterator[Session]:
    with Session(request.app.state.engine) as session:
        yield session
