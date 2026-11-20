"""Copia uma base SQLite migrada para um PostgreSQL migrado e vazio, preservando IDs."""
import os
from pathlib import Path

from sqlalchemy import create_engine, func, insert, select, text
from sqlalchemy.engine import make_url

from app.db.models import Observation, Station


def transfer(source_url: str, target_url: str) -> dict[str, int]:
    source, target = make_url(source_url), make_url(target_url)
    if source.drivername != "sqlite" or not source.database or not Path(source.database).is_file():
        raise ValueError("A origem deve ser um arquivo SQLite existente")
    if target.drivername != "postgresql+psycopg":
        raise ValueError("O destino deve usar postgresql+psycopg")
    reader = create_engine(source, hide_parameters=True)
    writer = create_engine(target, hide_parameters=True)
    counts = {}
    try:
        with reader.connect() as src, writer.begin() as dest:
            src.exec_driver_sql("BEGIN")  # Snapshot including SELECT with sqlite3's legacy transaction mode.
            revision = text("SELECT version_num FROM alembic_version")
            if src.scalar(revision) != "0001_weather" or dest.scalar(revision) != "0001_weather":
                raise ValueError("Esta versão do importador requer revisão 0001_weather nas duas bases")
            dest.execute(text("LOCK TABLE stations, observations IN ACCESS EXCLUSIVE MODE"))
            tables = (Station.__table__, Observation.__table__)
            for table in tables:
                if dest.scalar(select(func.count()).select_from(table)):
                    raise ValueError("O destino deve estar vazio")
            for table in tables:
                count = 0
                for batch in src.execute(select(table).order_by(table.c.id)).mappings().partitions(500):
                    dest.execute(insert(table), [dict(row) for row in batch])
                    count += len(batch)
                if dest.scalar(select(func.count()).select_from(table)) != count:
                    raise RuntimeError(f"Contagem divergente em {table.name}")
                counts[table.name] = count
                maximum = dest.scalar(select(func.max(table.c.id)))
                if maximum is not None:
                    dest.execute(text("SELECT setval(pg_get_serial_sequence(:tbl, 'id'), :maximum, true)"),
                                 {"tbl": table.name, "maximum": maximum})
    finally:
        reader.dispose()
        writer.dispose()
    return counts


if __name__ == "__main__":
    print(transfer(os.environ["SOURCE_DATABASE_URL"], os.environ["DATABASE_URL"]))
