"""Weather symbol mappings for GeoSphere Austria forecast data.

The forecast dataset (nwp-v1-1h-2500m) provides the weather symbol
parameter ``sy`` as a numeric code. The official (German only) code list
is documented in
https://github.com/Geosphere-Austria/dataset-api-docs/issues/30
"""

from __future__ import annotations

SYMBOL_TEXT_DE: dict[int, str] = {
    1: "Wolkenlos",
    2: "Heiter",
    3: "Wolkig",
    4: "Stark bewölkt",
    5: "Bedeckt",
    6: "Bodennebel",
    7: "Hochnebel",
    8: "Leichter Regen",
    9: "Mäßiger Regen",
    10: "Starker Regen",
    11: "Schneeregen",
    12: "Schneeregen",
    13: "Schneeregen",
    14: "Leichter Schneefall",
    15: "Mäßiger Schneefall",
    16: "Starker Schneefall",
    17: "Regenschauer",
    18: "Regenschauer",
    19: "Starker Regenschauer",
    20: "Schneeregenschauer",
    21: "Schneeregenschauer",
    22: "Schneeregenschauer",
    23: "Schneeschauer",
    24: "Schneeschauer",
    25: "Starker Schneeschauer",
    26: "Gewitter",
    27: "Gewitter",
    28: "Starkes Gewitter",
    29: "Gewitter mit Schneeregen",
    30: "Starkes Gewitter mit Schneeregen",
    31: "Gewitter mit Schneefall",
    32: "Starkes Gewitter mit Schneefall",
}
"""Official German symbol descriptions from GeoSphere Austria."""

SYMBOL_TEXT_EN: dict[int, str] = {
    1: "Clear",
    2: "Mostly clear",
    3: "Partly cloudy",
    4: "Mostly cloudy",
    5: "Overcast",
    6: "Ground fog",
    7: "High fog",
    8: "Light rain",
    9: "Moderate rain",
    10: "Heavy rain",
    11: "Sleet",
    12: "Sleet",
    13: "Sleet",
    14: "Light snowfall",
    15: "Moderate snowfall",
    16: "Heavy snowfall",
    17: "Rain showers",
    18: "Rain showers",
    19: "Heavy rain showers",
    20: "Sleet showers",
    21: "Sleet showers",
    22: "Sleet showers",
    23: "Snow showers",
    24: "Snow showers",
    25: "Heavy snow showers",
    26: "Thunderstorm",
    27: "Thunderstorm",
    28: "Heavy thunderstorm",
    29: "Thunderstorm with sleet",
    30: "Heavy thunderstorm with sleet",
    31: "Thunderstorm with snowfall",
    32: "Heavy thunderstorm with snowfall",
}
"""Unofficial English translations of the symbol descriptions."""

SYMBOL_CONDITION: dict[int, str] = {
    1: "sunny",
    2: "sunny",
    3: "partlycloudy",
    4: "cloudy",
    5: "cloudy",
    6: "fog",
    7: "fog",
    8: "rainy",
    9: "rainy",
    10: "pouring",
    11: "snowy-rainy",
    12: "snowy-rainy",
    13: "snowy-rainy",
    14: "snowy",
    15: "snowy",
    16: "snowy",
    17: "rainy",
    18: "rainy",
    19: "pouring",
    20: "snowy-rainy",
    21: "snowy-rainy",
    22: "snowy-rainy",
    23: "snowy",
    24: "snowy",
    25: "snowy",
    26: "lightning-rainy",
    27: "lightning-rainy",
    28: "lightning-rainy",
    29: "lightning-rainy",
    30: "lightning-rainy",
    31: "lightning-rainy",
    32: "lightning-rainy",
}
"""Symbol codes mapped to Home Assistant weather condition strings.

A consumer has to change "sunny" to "clear-night" at nighttime itself,
as this library does not know the position of the sun.
"""


def symbol_to_text(symbol: float | int | None, lang: str = "en") -> str | None:
    """Translate a weather symbol code into a description.

    Args:
        symbol: The numeric weather symbol code (``sy`` parameter).
        lang: "en" for English (unofficial translation) or
            "de" for the official German description.

    Returns:
        The description of the weather symbol,
        or None for an unknown symbol code.
    """
    if symbol is None:
        return None
    text = SYMBOL_TEXT_DE if lang == "de" else SYMBOL_TEXT_EN
    return text.get(int(round(symbol)))


def symbol_to_condition(symbol: float | int | None) -> str | None:
    """Translate a weather symbol code into a Home Assistant weather condition.

    Args:
        symbol: The numeric weather symbol code (``sy`` parameter).

    Returns:
        The Home Assistant weather condition string,
        or None for an unknown symbol code.
    """
    if symbol is None:
        return None
    return SYMBOL_CONDITION.get(int(round(symbol)))
