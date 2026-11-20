from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import AwareDatetime
from sqlalchemy.orm import Session

from app.db.models import Station
from app.db.session import get_session
from app.repositories import observations as repo
from app.schemas import History, ObservationOut, StationOut, Summary
from app.services.export import CSV_HEADERS, export_csv

router = APIRouter(prefix="/api/v1/stations", tags=["Estações"])
Database = Annotated[Session, Depends(get_session)]


def period_filter(
    start: Annotated[AwareDatetime | None, Query(description="Início inclusivo da medição, com fuso explícito. O servidor compara em UTC.")] = None,
    end: Annotated[AwareDatetime | None, Query(description="Fim inclusivo da medição, com fuso explícito. O servidor compara em UTC.")] = None,
) -> repo.Period:
    if start and end and start > end:
        raise HTTPException(422, "start deve anteceder end")
    return repo.Period(start, end)


def require_station(station_id: Annotated[int, Path(ge=1, le=2**63 - 1)], db: Database) -> Station:
    station = repo.get_station(db, station_id)
    if station is None:
        raise HTTPException(404, "Estação desconhecida")
    return station


SelectedStation = Annotated[Station, Depends(require_station)]
Period = Annotated[repo.Period, Depends(period_filter)]


@router.get("", response_model=list[StationOut])
def stations(db: Database):
    return repo.list_stations(db)


@router.get("/{station_id}", response_model=StationOut)
def detail(station: SelectedStation):
    return station


@router.get("/{station_id}/latest", response_model=ObservationOut)
def latest(station: SelectedStation, db: Database):
    observation = repo.latest(db, station.id, repo.Period())
    if observation is None:
        raise HTTPException(404, "Estação sem observações")
    return observation


@router.get("/{station_id}/observations", response_model=History)
def history(request: Request, station: SelectedStation, db: Database, period: Period,
            page: Annotated[int, Query(ge=1)] = 1,
            page_size: Annotated[int | None, Query(ge=1)] = None,
            order: Literal["asc", "desc"] = "asc"):
    maximum = request.app.state.settings.max_page_size
    size = min(100, maximum) if page_size is None else page_size
    offset = (page - 1) * size
    if size > maximum or offset > 2**63 - 1:
        raise HTTPException(422, "Paginação excede o limite")
    return {"page": page, "page_size": size,
            "items": repo.history(db, station.id, period, offset, size, order == "desc")}


@router.get("/{station_id}/summary", response_model=Summary)
def summary(station: SelectedStation, db: Database, period: Period):
    return repo.summary(db, station.id, period)


@router.get("/{station_id}/export.csv", response_class=StreamingResponse,
            responses={200: {"description": "CSV UTF-8. Colunas em ordem: " + ", ".join(CSV_HEADERS),
                             "content": {"text/csv": {"schema": {"type": "string"}}}}})
def export(station: SelectedStation, db: Database, period: Period):
    rows = repo.batches(db, station.id, period)
    return StreamingResponse(export_csv(rows), media_type="text/csv; charset=utf-8",
                             headers={"Content-Disposition": f'attachment; filename="estacao-{station.id}.csv"'})
