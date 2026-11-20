"""Compare published routes and documentation examples with each FastAPI service."""
import json
import re
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from fastapi import routing
from sqlalchemy.orm import Session
from starlette.routing import Mount
from starlette.staticfiles import StaticFiles

from app.api import monitoring
from app.core.config import Settings
from app.main import create_app
from app.services.ingestion import ingest
from conftest import migrate


ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
GUIDE = ROOT / "docs" / "FRONTEND_INTEGRATION.md"


def inventory(document, services):
    rows = re.findall(r"^\| ([A-Z, ]+) \| `([^`]+)` \| ([^|]+) \|", document, re.M)
    return {(method, path) for methods, path, service in rows if service in services
            for method in methods.split(", ")}


@pytest.mark.parametrize(("role", "services"), [
    ("development", {"Público", "Ingestão", "DEV"}),
    ("ingest", {"Ingestão"}),
    ("public", {"Público"}),
])
def test_documented_routes(role, services):
    app = create_app(Settings(_env_file=None), role=role)
    # FastAPI releases use either flattened routes or lazy router contexts.
    contexts = getattr(routing, "iter_route_contexts", iter)(app.routes)
    actual = set()
    for route in contexts:
        if isinstance(getattr(route, "original_route", route), Mount):
            assert isinstance(route.app, StaticFiles)
            actual.update((method, route.path + "/{path}") for method in ("GET", "HEAD"))
        else:
            actual.update((method, route.path) for method in route.methods)
    assert inventory(README.read_text(encoding="utf-8"), services) == actual
    published = {(method.upper(), path) for path, operations in app.openapi()["paths"].items()
                 for method in operations}
    assert published <= actual
    if role == "public":
        assert published == actual == inventory(GUIDE.read_text(encoding="utf-8"), services)


def typescript_type(schema):
    """Represent the small set of OpenAPI value types used in the public DTOs."""
    if "$ref" in schema:
        return schema["$ref"].rsplit("/", 1)[1]
    if "enum" in schema:
        return " | ".join(json.dumps(value) for value in schema["enum"])
    if "anyOf" in schema:
        return " | ".join(typescript_type(option) for option in schema["anyOf"])
    if schema.get("format") == "date-time":
        return "UTCString"
    if schema["type"] == "array":
        return typescript_type(schema["items"]) + "[]"
    return "number" if schema["type"] == "integer" else schema["type"]


@pytest.mark.parametrize("file", [README, GUIDE], ids=["readme", "frontend"])
def test_documented_types_match_public_openapi(file):
    schemas = create_app(Settings(_env_file=None), role="public").openapi()["components"]["schemas"]
    document = file.read_text(encoding="utf-8")
    assert "type UTCString = string" in document
    for name, schema in schemas.items():
        interface = "ObservationPage" if name == "History" else name
        fields = re.search(rf"interface {interface} \{{([^}}]+)\}}", document)[1]
        documented = dict(line.strip().split(": ", 1) for line in fields.strip().splitlines())
        expected = {}
        for key, prop in schema["properties"].items():
            declaration = key if key in schema["required"] else key + "?"
            expected[declaration] = typescript_type(prop)
        assert documented == expected, interface


@pytest.mark.anyio
async def test_public_examples_against_http(database_url, payload, monkeypatch):
    migrate(database_url)
    settings = Settings(_env_file=None, database_url=database_url, allow_simulated=True)
    writer = create_app(settings, role="ingest")
    async with writer.router.lifespan_context(writer):
        with Session(writer.state.engine) as session:
            ingest(session, list(payload.items()) + [("dev_simulated", "1")],
                   datetime(2026, 11, 20, 14, 30, 2, tzinfo=UTC), settings)

    class ExampleClock(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 11, 20, 14, 31, tzinfo=UTC).astimezone(tz)

    monkeypatch.setattr(monitoring, "datetime", ExampleClock)
    reader = create_app(settings, role="public")
    async with reader.router.lifespan_context(reader):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=reader),
                                     base_url="http://localhost") as client:
            for file in (README, GUIDE):
                document = file.read_text(encoding="utf-8")
                contracts = document.split("## Consultas públicas, rota por rota\n", 1)[1]
                contracts = re.split(r"^#{1,2} ", contracts, flags=re.M)[0]
                sections = re.findall(r"^### GET `([^`]+)`\n(.*?)(?=^### |\Z)",
                                      contracts, re.M | re.S)
                assert {path for path, _ in sections} == set(reader.openapi()["paths"])
                for path, contract in sections:
                    url = re.search(r"(?:^GET |`GET )(/api/v1/stations[^\s`]*)", contract, re.M)[1]
                    response = await client.get(url)
                    assert response.status_code == 200, (file, url, response.text)
                    if path.endswith(".csv"):
                        sample = re.search(r"```csv\n(.*?)\n```", contract, re.S)[1]
                        assert response.text == sample.replace("\n", "\r\n") + "\r\n"
                    else:
                        sample = re.search(r"```json\n(.*?)\n```", contract, re.S)[1]
                        assert response.json() == json.loads(sample), (file, url)
