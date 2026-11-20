from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal, TypeVar

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from fastapi.responses import Response, StreamingResponse
from pydantic import AwareDatetime
from sqlalchemy.orm import Session

from app.db.models import Station
from app.db.session import get_session
from app.repositories import observations as repo
from app.schemas import History, ObservationOut, StationOut, Summary
from app.services.export import CSV_HEADERS, export_csv

router = APIRouter(prefix="/api/v1/stations", tags=["Estações"])
observations = APIRouter(prefix="/api/v1/stations", tags=["Observações"])
public_exports = APIRouter(prefix="/api/v1/stations", tags=["Observações"])
Database = Annotated[Session, Depends(get_session, scope="function")]
T = TypeVar("T")


def period_filter(
    request: Request,
    start: Annotated[AwareDatetime | None, Query(description="Início inclusivo da medição, com fuso explícito. O servidor compara em UTC.")] = None,
    end: Annotated[AwareDatetime | None, Query(description="Fim inclusivo da medição, com fuso explícito. O servidor compara em UTC.")] = None,
) -> repo.Period:
    if request.app.state.public:
        span = timedelta(days=request.app.state.settings.max_period_days)
        try:
            if start is None and end is None:
                start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
                end = start + timedelta(days=1) - timedelta(microseconds=1)
            elif start is None:
                start = end - span
            elif end is None:
                end = start + span
            start, end = start.astimezone(UTC), end.astimezone(UTC)
        except (ValueError, OverflowError):
            raise HTTPException(422, "Instante fora do intervalo suportado") from None
        if end - start > span:
            raise HTTPException(422, "Reduza o período consultado")
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


def cached(request: Request, db: Session, key: tuple, ttl: int, load: Callable[[], T]) -> T:
    if not request.app.state.public or not ttl:
        return load()
    version = repo.observation_version(db)
    return request.app.state.cache.get((version, *key), ttl, load)


@observations.get("/{station_id}/latest", response_model=ObservationOut)
def latest(request: Request, station: SelectedStation, db: Database):
    def read():
        observation = repo.latest(db, station.id, repo.Period())
        if observation is None:
            raise HTTPException(404, "Estação sem observações")
        return ObservationOut.model_validate(observation)

    return cached(request, db, ("latest", station.id), request.app.state.settings.cache_ttl_seconds, read)


@observations.get("/{station_id}/observations", response_model=History)
def history(request: Request, station: SelectedStation, db: Database, period: Period,
            page: Annotated[int, Query(ge=1)] = 1,
            page_size: Annotated[int | None, Query(ge=1)] = None,
            order: Literal["asc", "desc"] = "asc"):
    maximum = request.app.state.settings.max_page_size
    size = min(100, maximum) if page_size is None else page_size
    offset = (page - 1) * size
    if size > maximum or offset > 2**63 - 1:
        raise HTTPException(422, "Paginação excede o limite")

    def read():
        return History(page=page, page_size=size,
                       items=repo.history(db, station.id, period, offset, size, order == "desc"))

    return cached(request, db, ("history", station.id, period, page, size, order),
                  request.app.state.settings.history_cache_ttl_seconds, read)


@observations.get("/{station_id}/summary", response_model=Summary)
def summary(request: Request, station: SelectedStation, db: Database, period: Period):
    return cached(request, db, ("summary", station.id, period), request.app.state.settings.summary_cache_ttl_seconds,
                  lambda: repo.summary(db, station.id, period))


CSV_RESPONSES = {200: {"description": "CSV UTF-8. Colunas em ordem: " + ", ".join(CSV_HEADERS),
                       "content": {"text/csv": {"schema": {"type": "string"}}}}}


@public_exports.get("/{station_id}/export.csv", response_class=Response, responses=CSV_RESPONSES)
def public_export(request: Request, station: SelectedStation, db: Database, period: Period):
    maximum = request.app.state.settings.max_csv_rows
    batch = repo.history(db, station.id, period, 0, maximum + 1, False)
    if len(batch) > maximum:
        raise HTTPException(422, "Reduza o período para exportar menos linhas")
    return Response("".join(export_csv([batch])), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="estacao-{station.id}.csv"'})


@router.get("/{station_id}/export.csv", response_class=StreamingResponse, responses=CSV_RESPONSES)
def export(station: SelectedStation, db: Annotated[Session, Depends(get_session)], period: Period):
    rows = repo.batches(db, station.id, period)
    return StreamingResponse(export_csv(rows), media_type="text/csv; charset=utf-8",
                             headers={"Content-Disposition": f'attachment; filename="estacao-{station.id}.csv"'})
