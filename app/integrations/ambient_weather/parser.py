import math
import re
from datetime import UTC, datetime
from urllib.parse import parse_qsl

from app.schemas import Measurements, Report

from .fields import FIELDS

IDENTIFIERS = {"MAC", "dateutc", "dev_simulated"}


class InvalidReport(ValueError):
    """Message may be logged. Never include user-supplied values."""


def decode_query(query: bytes) -> list[tuple[str, str]]:
    # Avoid silently replacing invalid UTF-8 in the archived parameters.
    if re.search(rb"%(?![0-9a-fA-F]{2})", query):
        raise InvalidReport("Escape percentual inválido")
    try:
        return parse_qsl(query.decode("utf-8"), keep_blank_values=True, errors="strict")
    except UnicodeError:
        raise InvalidReport("Codificação UTF-8 inválida") from None


def normalize_mac(value: str) -> str:
    if not re.fullmatch(r"(?:[0-9a-fA-F]{2}([:-]))(?:[0-9a-fA-F]{2}\1){4}[0-9a-fA-F]{2}|[0-9a-fA-F]{12}", value):
        raise InvalidReport("MAC inválido")
    digits = value.replace(":", "").replace("-", "").upper()
    return ":".join(digits[i:i + 2] for i in range(0, 12, 2))


def parse_report(pairs: list[tuple[str, str]]) -> Report:
    raw: dict[str, str | list[str]] = {}
    known: dict[str, str] = {}
    unknown = set()
    for key, value in pairs:
        if not key or "\x00" in key or "\x00" in value:
            raise InvalidReport("Parâmetro inválido")
        if key in FIELDS or key in IDENTIFIERS:
            if key in known:
                raise InvalidReport(f"Parâmetro repetido: {key}")
            known[key] = value
        else:
            unknown.add(key)
        previous = raw.get(key)
        if isinstance(previous, list):
            previous.append(value)
        else:
            raw[key] = value if previous is None else [previous, value]

    mac = normalize_mac(known.get("MAC", ""))
    try:
        measured = datetime.strptime(known.get("dateutc", ""), "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC)
    except ValueError:
        raise InvalidReport("dateutc inválido ou ausente") from None

    values = {}
    for key, spec in FIELDS.items():
        if key not in known:
            continue
        try:
            number = float(known[key])
            converted = spec.convert(number)
        except ValueError:
            raise InvalidReport(f"Valor numérico inválido: {key}") from None
        if (not math.isfinite(converted)
                or (spec.minimum is not None and number < spec.minimum)
                or (spec.maximum is not None and number > spec.maximum)):
            raise InvalidReport(f"Valor fora do intervalo: {key}")
        values[spec.column] = converted

    if not values and not unknown:
        raise InvalidReport("Transmissão sem parâmetros de sensores")
    if "dev_simulated" in known and known["dev_simulated"] != "1":
        raise InvalidReport("Marcador de simulação inválido")
    return Report(mac_address=mac, measured_at_utc=measured, measurements=Measurements(**values),
                  raw_payload=raw, unknown_fields=sorted(unknown), is_simulated="dev_simulated" in known)
