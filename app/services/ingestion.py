from datetime import datetime

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.logging import log
from app.integrations.ambient_weather.parser import InvalidReport, parse_report
from app.repositories.ingestion import save_report


def ingest(db: Session, pairs: list[tuple[str, str]], received: datetime, settings: Settings) -> None:
    report = parse_report(pairs)
    if report.is_simulated and not settings.allow_simulated:
        raise InvalidReport("Simulação desabilitada nesta instância")
    if settings.diagnostic_payload:
        log("ingestion_payload", fields=report.measurements.model_dump(exclude_none=True))
    if report.unknown_fields:
        log("unknown_fields", fields=report.unknown_fields)
    with db.begin():
        station_id, created = save_report(db, report, received)
    log("observation_saved" if created else "observation_duplicate", station_id=station_id,
        measured_at_utc=report.measured_at_utc.isoformat(), parameters=len(pairs))
