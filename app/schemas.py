from typing import Annotated, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field
from pydantic.fields import FieldInfo


def metric(label: str, unit: str) -> FieldInfo:
    return Field(description=f"{label} ({unit})", json_schema_extra={"x-unit": unit})


class StationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    mac_address: str
    name: str
    model: str
    is_simulated: bool
    created_at: AwareDatetime = Field(description="Instante de cadastro da estação em UTC.")
    updated_at: AwareDatetime = Field(description="Instante da última atualização em UTC.")
    last_seen_at: AwareDatetime = Field(description="Instante da última transmissão aceita em UTC.")


class PublicStation(BaseModel):
    id: int
    name: str
    model: str
    is_simulated: bool
    last_seen_at: AwareDatetime = Field(description="Última comunicação aceita, em UTC.")
    communication: Literal["online", "delayed", "offline"]
    seconds_since_contact: int = Field(description="Tempo desde o último contato, em segundos.")
    last_measured_at_utc: AwareDatetime | None = Field(description="Maior instante de medição em UTC.")
    seconds_since_measurement: int | None = Field(description="Idade da medição em segundos. Negativa indica relógio adiantado.")


class PublicError(BaseModel):
    detail: str


class Measurements(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False, extra="forbid")

    outdoor_temperature_c: Annotated[float | None, metric("Temperatura externa", "°C")] = None
    indoor_temperature_c: Annotated[float | None, metric("Temperatura interna", "°C")] = None
    outdoor_humidity_pct: Annotated[float | None, metric("Umidade externa", "%")] = None
    indoor_humidity_pct: Annotated[float | None, metric("Umidade interna", "%")] = None
    wind_speed_ms: Annotated[float | None, metric("Velocidade do vento", "m/s")] = None
    wind_gust_ms: Annotated[float | None, metric("Rajada", "m/s")] = None
    wind_direction_deg: Annotated[float | None, metric("Direção do vento", "°")] = None
    wind_gust_direction_deg: Annotated[float | None, metric("Direção da rajada", "°")] = None
    daily_rain_mm: Annotated[float | None, metric("Chuva acumulada diária", "mm")] = None
    hourly_rain_mm: Annotated[float | None, metric("Chuva acumulada horária", "mm")] = None
    weekly_rain_mm: Annotated[float | None, metric("Chuva acumulada semanal", "mm")] = None
    monthly_rain_mm: Annotated[float | None, metric("Chuva acumulada mensal", "mm")] = None
    yearly_rain_mm: Annotated[float | None, metric("Chuva acumulada anual", "mm")] = None
    absolute_pressure_hpa: Annotated[float | None, metric("Pressão absoluta", "hPa")] = None
    relative_pressure_hpa: Annotated[float | None, metric("Pressão relativa", "hPa")] = None
    uv_index: Annotated[float | None, metric("Índice UV", "adimensional")] = None
    solar_radiation_wm2: Annotated[float | None, metric("Radiação solar", "W/m²")] = None


class Report(BaseModel):
    mac_address: str
    measured_at_utc: AwareDatetime
    measurements: Measurements
    raw_payload: dict[str, str | list[str]]
    unknown_fields: list[str]
    is_simulated: bool


class ObservationOut(Measurements):
    model_config = ConfigDict(from_attributes=True)

    id: int
    station_id: int
    measured_at_utc: AwareDatetime = Field(description="Instante da medição no console em UTC.")
    received_at_utc: AwareDatetime = Field(description="Instante de recebimento no servidor em UTC.")


class History(BaseModel):
    page: int
    page_size: int
    items: list[ObservationOut]


class Summary(BaseModel):
    sample_count: int = Field(description="Quantidade de observações no período.")
    temperature_min_c: Annotated[float | None, metric("Temperatura externa mínima", "°C")]
    temperature_avg_c: Annotated[float | None, metric("Temperatura externa média", "°C")]
    temperature_max_c: Annotated[float | None, metric("Temperatura externa máxima", "°C")]
    humidity_min_pct: Annotated[float | None, metric("Umidade externa mínima", "%")]
    humidity_avg_pct: Annotated[float | None, metric("Umidade externa média", "%")]
    humidity_max_pct: Annotated[float | None, metric("Umidade externa máxima", "%")]
    wind_avg_ms: Annotated[float | None, metric("Velocidade média do vento", "m/s")]
    wind_max_ms: Annotated[float | None, metric("Velocidade máxima do vento", "m/s")]
    latest: ObservationOut | None
