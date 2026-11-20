from pathlib import Path

import httpx
import pytest
from alembic import command
from alembic.config import Config

from app.core.config import Settings
from app.main import create_app


def migrate(url: str) -> Config:
    cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    cfg.attributes["database_url"] = url
    command.upgrade(cfg, "head")
    return cfg


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
def database_url(tmp_path):
    return f"sqlite:///{tmp_path.as_posix()}/weather.db"


@pytest.fixture
def app(database_url):
    migrate(database_url)
    return create_app(Settings(_env_file=None, database_url=database_url, max_page_size=2,
                               ingest_networks=["127.0.0.1/32"], allow_simulated=False,
                               ack_text="OK", max_query_bytes=8192, max_parameters=128))


@pytest.fixture
async def client(app):
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                     base_url="http://localhost", follow_redirects=False) as client:
            yield client


@pytest.fixture
def payload():
    return {"MAC": "02:aa:cc:12:00:01", "dateutc": "2026-11-20 14:30:00", "tempf": "86",
            "humidity": "60", "windspeedmph": "12", "dailyrainin": "0.10"}
