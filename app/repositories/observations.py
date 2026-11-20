from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Observation, Station
from app.schemas import Summary


@dataclass(frozen=True)
class Period:
    start: datetime | None = None
    end: datetime | None = None


def list_stations(db: Session) -> Sequence[Station]:
    return db.scalars(select(Station).order_by(Station.id)).all()


def get_station(db: Session, station_id: int) -> Station | None:
    return db.get(Station, station_id)


def conditions(station_id: int, period: Period):
    filters = [Observation.station_id == station_id]
    if period.start is not None:
        filters.append(Observation.measured_at_utc >= period.start)
    if period.end is not None:
        filters.append(Observation.measured_at_utc <= period.end)
    return filters


def latest(db: Session, station_id: int, period: Period) -> Observation | None:
    query = select(Observation).where(*conditions(station_id, period)).order_by(
        Observation.received_at_utc.desc(), Observation.id.desc()
    ).limit(1)
    return db.scalar(query)


def chronological(station_id: int, period: Period, descending: bool = False):
    timestamp = Observation.measured_at_utc
    return select(Observation).where(*conditions(station_id, period)).order_by(
        timestamp.desc() if descending else timestamp
    )


def history(db: Session, station_id: int, period: Period, offset: int, limit: int,
            descending: bool) -> Sequence[Observation]:
    return db.scalars(chronological(station_id, period, descending).offset(offset).limit(limit)).all()


def batches(db: Session, station_id: int, period: Period) -> Iterator[Sequence[Observation]]:
    query = chronological(station_id, period).execution_options(yield_per=256)
    return db.scalars(query).partitions(256)


def summary(db: Session, station_id: int, period: Period) -> Summary:
    temp = Observation.outdoor_temperature_c
    humidity = Observation.outdoor_humidity_pct
    wind = Observation.wind_speed_ms
    stats = select(
        func.count().label("sample_count"),
        func.min(temp).label("temperature_min_c"), func.avg(temp).label("temperature_avg_c"),
        func.max(temp).label("temperature_max_c"),
        func.min(humidity).label("humidity_min_pct"), func.avg(humidity).label("humidity_avg_pct"),
        func.max(humidity).label("humidity_max_pct"),
        func.avg(wind).label("wind_avg_ms"), func.max(wind).label("wind_max_ms"),
    ).where(*conditions(station_id, period))
    return Summary(**db.execute(stats).mappings().one(), latest=latest(db, station_id, period))
