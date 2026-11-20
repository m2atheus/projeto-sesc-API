from collections.abc import Callable
from dataclasses import dataclass

from .converters import fahrenheit_to_celsius, inches_to_mm, inhg_to_hpa, mph_to_ms


@dataclass(frozen=True)
class SensorField:
    column: str
    convert: Callable[[float], float]
    minimum: float | None = None
    maximum: float | None = None


FIELDS = {
    "tempf": SensorField("outdoor_temperature_c", fahrenheit_to_celsius),
    "tempinf": SensorField("indoor_temperature_c", fahrenheit_to_celsius),
    "humidity": SensorField("outdoor_humidity_pct", float, 0, 100),
    "humidityin": SensorField("indoor_humidity_pct", float, 0, 100),
    "windspeedmph": SensorField("wind_speed_ms", mph_to_ms, 0),
    "windgustmph": SensorField("wind_gust_ms", mph_to_ms, 0),
    "winddir": SensorField("wind_direction_deg", float, 0, 360),
    "windgustdir": SensorField("wind_gust_direction_deg", float, 0, 360),
    "dailyrainin": SensorField("daily_rain_mm", inches_to_mm, 0),
    "hourlyrainin": SensorField("hourly_rain_mm", inches_to_mm, 0),
    "weeklyrainin": SensorField("weekly_rain_mm", inches_to_mm, 0),
    "monthlyrainin": SensorField("monthly_rain_mm", inches_to_mm, 0),
    "yearlyrainin": SensorField("yearly_rain_mm", inches_to_mm, 0),
    "baromabsin": SensorField("absolute_pressure_hpa", inhg_to_hpa, 0),
    "baromrelin": SensorField("relative_pressure_hpa", inhg_to_hpa, 0),
    "uv": SensorField("uv_index", float, 0),
    "solarradiation": SensorField("solar_radiation_wm2", float, 0),
}
