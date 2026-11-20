from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import TypeDecorator


class UTCDateTime(TypeDecorator[datetime]):
    """Persist UTC and restore timezone information discarded by SQLite."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if value.utcoffset() is None:
            raise ValueError("Timestamp sem fuso horário")
        return value.astimezone(UTC)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class Base(DeclarativeBase):
    pass


class Station(Base):
    __tablename__ = "stations"

    id: Mapped[int] = mapped_column(primary_key=True)
    mac_address: Mapped[str] = mapped_column(String(17), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    model: Mapped[str] = mapped_column(String(50))
    is_simulated: Mapped[bool]
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime)
    last_seen_at: Mapped[datetime] = mapped_column(UTCDateTime)


class Observation(Base):
    __tablename__ = "observations"
    __table_args__ = (
        UniqueConstraint("station_id", "measured_at_utc", name="uq_observation_station_time"),
        Index("ix_observations_received", "station_id", "received_at_utc", "id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    station_id: Mapped[int] = mapped_column(ForeignKey("stations.id"))
    measured_at_utc: Mapped[datetime] = mapped_column(UTCDateTime)
    received_at_utc: Mapped[datetime] = mapped_column(UTCDateTime)
    outdoor_temperature_c: Mapped[float | None]
    indoor_temperature_c: Mapped[float | None]
    outdoor_humidity_pct: Mapped[float | None]
    indoor_humidity_pct: Mapped[float | None]
    wind_speed_ms: Mapped[float | None]
    wind_gust_ms: Mapped[float | None]
    wind_direction_deg: Mapped[float | None]
    wind_gust_direction_deg: Mapped[float | None]
    daily_rain_mm: Mapped[float | None]
    hourly_rain_mm: Mapped[float | None]
    weekly_rain_mm: Mapped[float | None]
    monthly_rain_mm: Mapped[float | None]
    yearly_rain_mm: Mapped[float | None]
    absolute_pressure_hpa: Mapped[float | None]
    relative_pressure_hpa: Mapped[float | None]
    uv_index: Mapped[float | None]
    solar_radiation_wm2: Mapped[float | None]
    raw_payload: Mapped[dict] = mapped_column(JSON, deferred=True)
