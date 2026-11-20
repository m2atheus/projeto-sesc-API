"""Inicie um único processo de ingestão ou consulta com a configuração do serviço."""
import argparse

import uvicorn

from app.core.config import Settings
from app.core.logging import logger


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("role", choices=("dev", "ingest", "public"))
    role = parser.parse_args().role
    settings = Settings()
    logger.setLevel(settings.log_level)
    if role == "dev" and settings.app_env != "development":
        parser.error("O modo dev com Swagger requer APP_ENV=development")
    servers = {
        "dev": ("app.main:create_app", "127.0.0.1", settings.dev_port),
        "ingest": ("app.main:create_ingest_app", settings.ingest_host, settings.ingest_port),
        "public": ("app.main:create_public_app", settings.public_host, settings.public_port),
    }
    factory, host, port = servers[role]
    proxy = role == "public" and bool(settings.trusted_proxy_ips)
    uvicorn.run(factory, factory=True, host=host, port=port,
                workers=1, proxy_headers=proxy,
                forwarded_allow_ips=",".join(map(str, settings.trusted_proxy_ips)) if proxy else "",
                access_log=False, log_level=settings.log_level.lower(),
                limit_concurrency=64, timeout_graceful_shutdown=30)


if __name__ == "__main__":
    main()
