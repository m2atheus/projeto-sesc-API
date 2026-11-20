from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.session import get_session
from app.repositories.observations import station_activity
from app.schemas import PublicStation

public = APIRouter(prefix="/api/v1/stations", tags=["Estações públicas"])
internal = APIRouter(tags=["Monitoramento interno"])
Database = Annotated[Session, Depends(get_session, scope="function")]


def describe(row, settings: Settings, now: datetime) -> PublicStation:
    station, measured = row
    elapsed = max(0, int((now - station.last_seen_at).total_seconds()))
    state = "online"
    if elapsed >= settings.station_timeout_seconds:
        state = "offline"
    elif elapsed >= settings.station_delay_seconds:
        state = "delayed"
    return PublicStation(id=station.id, name=station.name, model=station.model, is_simulated=station.is_simulated,
                         last_seen_at=station.last_seen_at, communication=state,
                         seconds_since_contact=elapsed, last_measured_at_utc=measured,
                         seconds_since_measurement=int((now - measured).total_seconds()) if measured else None)


@public.get("", response_model=list[PublicStation])
@internal.get("/monitor/stations", response_model=list[PublicStation])
def stations(request: Request, db: Database, page: Annotated[int, Query(ge=1, le=1000000)] = 1,
             page_size: Annotated[int | None, Query(ge=1)] = None):
    settings = request.app.state.settings
    size = page_size or min(100, settings.max_page_size)
    if size > settings.max_page_size:
        raise HTTPException(422, "Página excede o limite")
    now = datetime.now(UTC)
    return [describe(row, settings, now) for row in station_activity(db, limit=size, offset=(page - 1) * size)]


@public.get("/{station_id}", response_model=PublicStation)
def station(request: Request, db: Database, station_id: Annotated[int, Path(ge=1, le=2**63 - 1)]):
    rows = station_activity(db, station_id=station_id)
    if not rows:
        raise HTTPException(404, "Estação desconhecida")
    return describe(rows[0], request.app.state.settings, datetime.now(UTC))
