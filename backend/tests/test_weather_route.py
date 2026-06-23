from __future__ import annotations

import pytest

from app.api.routes.weather import _parse_weather_number


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, 0),
        ("", 0),
        ("≤3", 3),
        ("47%", 47),
        ("3.6", 4),
        (" 12 ", 12),
        (True, 0),
        (7, 7),
    ],
)
def test_parse_weather_number_handles_common_weather_values(value, expected) -> None:
    assert _parse_weather_number(value) == expected

