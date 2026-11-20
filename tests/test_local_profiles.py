import sys
from pathlib import Path

import pytest

from app import serve
from app.core.config import Settings

ROOT = Path(__file__).resolve().parents[1]


def test_templates_keep_development_and_production_separate(monkeypatch):
    for field in Settings.model_fields:
        monkeypatch.delenv(field.upper(), raising=False)
    dev = Settings(_env_file=ROOT / ".env.example")
    prod = Settings(_env_file=ROOT / "deploy/production.env.example")

    assert dev.app_env == "development" and dev.allow_simulated
    assert prod.app_env == "production" and not prod.allow_simulated
    assert dev.database_url != prod.database_url and dev.backup_dir != prod.backup_dir
    assert dev.ingest_host == dev.public_host == "127.0.0.1"
    assert len({dev.dev_port, dev.ingest_port, dev.public_port}) == 3


@pytest.mark.parametrize(("role", "factory", "port"), [
    ("dev", "create_app", 9100),
    ("ingest", "create_ingest_app", 9101),
    ("public", "create_public_app", 9102),
])
def test_dev_launcher_reads_dotenv(tmp_path, monkeypatch, role, factory, port):
    monkeypatch.chdir(tmp_path)
    config = {"APP_ENV": "development", "DEV_PORT": "9100", "INGEST_PORT": "9101",
              "PUBLIC_PORT": "9102", "TRUSTED_PROXY_IPS": "[]"}
    for key in config:
        monkeypatch.delenv(key, raising=False)
    (tmp_path / ".env").write_text("\n".join(f"{k}={v}" for k, v in config.items()), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["app.serve", role])
    calls = []
    monkeypatch.setattr(serve.uvicorn, "run", lambda app, **options: calls.append((app, options)))
    serve.main()
    (app, options), = calls
    assert app == f"app.main:{factory}" and options["port"] == port
    assert options["proxy_headers"] is False


def test_combined_dev_launcher_requires_development(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setattr(sys, "argv", ["app.serve", "dev"])
    with pytest.raises(SystemExit) as exc:
        serve.main()
    assert exc.value.code == 2
