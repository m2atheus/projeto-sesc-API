from datetime import datetime

from sqlalchemy import case
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.db.models import Observation, Station
from app.schemas import Report


class StationSourceConflict(ValueError):
    pass


def save_report(db: Session, report: Report, received: datetime) -> tuple[int, bool]:
    """Called inside a transaction. Both supported engines arbitrate conflicts atomically."""
    insert = {"sqlite": sqlite_insert, "postgresql": pg_insert}[db.get_bind().dialect.name]
    station = insert(Station).values(
        mac_address=report.mac_address, model="WS-2000", is_simulated=report.is_simulated,
        name="Simulador WS-2000" if report.is_simulated else "WS-2000",
        created_at=received, updated_at=received, last_seen_at=received,
    )
    last_seen = case((Station.last_seen_at < station.excluded.last_seen_at, station.excluded.last_seen_at),
                     else_=Station.last_seen_at)
    station = station.on_conflict_do_update(
        index_elements=[Station.mac_address],
        set_={"last_seen_at": last_seen, "updated_at": last_seen},
        where=Station.is_simulated == station.excluded.is_simulated,
    ).returning(Station.id)
    station_id = db.scalar(station)
    if station_id is None:
        raise StationSourceConflict("MAC já cadastrado com outra origem")

    observation = insert(Observation).values(
        station_id=station_id, received_at_utc=received, measured_at_utc=report.measured_at_utc,
        raw_payload=report.raw_payload, **report.measurements.model_dump(exclude_unset=True),
    ).on_conflict_do_nothing(index_elements=[Observation.station_id, Observation.measured_at_utc])
    created = db.scalar(observation.returning(Observation.id)) is not None
    return station_id, created
