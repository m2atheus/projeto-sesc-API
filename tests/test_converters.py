import pytest

from app.integrations.ambient_weather.converters import (
    fahrenheit_to_celsius, inches_to_mm, inhg_to_hpa, mph_to_ms,
)


@pytest.mark.parametrize(("convert", "value", "expected"), [
    (fahrenheit_to_celsius, 86, 30), (fahrenheit_to_celsius, -40, -40),
    (mph_to_ms, 12, 5.36448), (inches_to_mm, 0.1, 2.54), (inhg_to_hpa, 29.92, 1013.20749),
])
def test_conversion(convert, value, expected):
    assert convert(value) == pytest.approx(expected)
