from ipaddress import IPv4Network, IPv6Network

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "sqlite:///./data/weather.db"
    ingest_networks: list[IPv4Network | IPv6Network] = [
        IPv4Network("127.0.0.1/32"), IPv6Network("::1/128"),
        IPv4Network("10.0.0.0/8"), IPv4Network("172.16.0.0/12"), IPv4Network("192.168.0.0/16"),
    ]
    cors_origins: list[str] = ["http://localhost:5173"]
    max_query_bytes: int = Field(8192, ge=1)
    max_parameters: int = Field(128, ge=2)
    max_page_size: int = Field(500, ge=1)
    ack_text: str = "OK"
    diagnostic_payload: bool = False
    allow_simulated: bool = False
