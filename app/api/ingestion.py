import logging
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.core.logging import log
from app.core.security import check_ingestion
from app.db.session import get_session
from app.integrations.ambient_weather.parser import InvalidReport, decode_query
from app.repositories.ingestion import StationSourceConflict
from app.services.ingestion import ingest

router = APIRouter(tags=["Console"], dependencies=[Depends(check_ingestion)])


@router.get("/data/report", include_in_schema=False)
@router.get("/data/report/", response_class=PlainTextResponse)
def receive_report(request: Request, db: Annotated[Session, Depends(get_session)]) -> PlainTextResponse:
    settings = request.app.state.settings
    received = datetime.now(UTC)
    query = request.scope["query_string"]
    parameter_count = query.count(b"&") + 1 if query else 0
    if parameter_count > settings.max_parameters:
        raise HTTPException(413, "Excesso de parâmetros")
    try:
        ingest(db, decode_query(query), received, settings)
    except (InvalidReport, StationSourceConflict) as exc:
        log("ingestion_rejected", level=logging.WARNING, reason=str(exc), parameters=parameter_count)
        raise HTTPException(409 if isinstance(exc, StationSourceConflict) else 422, str(exc)) from None
    return PlainTextResponse(settings.ack_text, headers={"Cache-Control": "no-store"})
