import csv
from collections.abc import Iterable, Iterator, Sequence
from io import StringIO

from app.db.models import Observation
from app.schemas import Measurements

CSV_HEADERS = (
    "Estação (ID)", "Medição (UTC)", "Recebimento (UTC)",
    *(field.description for field in Measurements.model_fields.values()),
)


def export_csv(batches: Iterable[Sequence[Observation]]) -> Iterator[str]:
    buffer = StringIO(newline="")
    writer = csv.writer(buffer)
    writer.writerow(CSV_HEADERS)
    yield buffer.getvalue()
    for batch in batches:
        buffer.seek(0)
        buffer.truncate()
        for obs in batch:
            writer.writerow([obs.station_id, obs.measured_at_utc.isoformat(), obs.received_at_utc.isoformat(),
                             *(getattr(obs, name) for name in Measurements.model_fields)])
        yield buffer.getvalue()
