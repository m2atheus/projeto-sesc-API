from ipaddress import IPv4Address, IPv4Network, IPv6Address, IPv6Network
from pathlib import Path
from typing import Literal, Self

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "sqlite:///./data/weather.db"
    ingest_networks: list[IPv4Network | IPv6Network] = [
        IPv4Network("127.0.0.1/32"), IPv6Network("::1/128"),
    ]
    cors_origins: list[str] = ["http://localhost:5173"]
    max_query_bytes: int = Field(8192, ge=1)
    max_parameters: int = Field(128, ge=2)
    max_page_size: int = Field(500, ge=1, le=2000)
    ack_text: str = "OK"
    diagnostic_payload: bool = False
    allow_simulated: bool = False
    app_env: Literal["production", "development"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    dev_port: int = Field(8000, ge=1, le=65535)
    ingest_host: str = "127.0.0.1"
    ingest_port: int = Field(8001, ge=1, le=65535)
    public_host: str = "127.0.0.1"
    public_port: int = Field(8080, ge=1, le=65535)
    trusted_proxy_ips: list[IPv4Address | IPv6Address] = [IPv4Address("127.0.0.1")]
    sqlite_busy_timeout_ms: int = Field(15000, ge=1, le=60000)
    max_period_days: int = Field(31, ge=1, le=366)
    max_csv_rows: int = Field(5000, ge=1, le=50000)
    public_requests_per_minute: int = Field(120, ge=1, le=10000)
    public_total_per_minute: int = Field(1200, ge=1, le=100000)
    cache_ttl_seconds: int = Field(60, ge=0, le=3600)
    summary_cache_ttl_seconds: int = Field(300, ge=0, le=3600)
    history_cache_ttl_seconds: int = Field(60, ge=0, le=3600)
    station_delay_seconds: int = Field(180, ge=1)
    station_timeout_seconds: int = Field(600, ge=2)
    backup_dir: Path = Path("backups")
    backup_secondary_dir: Path | None = None
    backup_retention_days: int = Field(30, ge=1)

    @model_validator(mode="after")
    def validate_thresholds(self) -> Self:
        if self.station_timeout_seconds <= self.station_delay_seconds:
            raise ValueError("STATION_TIMEOUT_SECONDS deve superar STATION_DELAY_SECONDS")
        if "*" in self.cors_origins:
            raise ValueError("Use origens CORS explícitas")
        return self
