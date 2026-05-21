from __future__ import annotations

from dataclasses import dataclass
from typing import Any

try:
    import requests
except ImportError:  # pragma: no cover - exercised only before dependencies exist
    requests = None  # type: ignore[assignment]

from config_loader import is_placeholder_api_key


CURRENT_CONDITIONS_URL = "https://weather.googleapis.com/v1/currentConditions:lookup"
DAILY_FORECAST_URL = "https://weather.googleapis.com/v1/forecast/days:lookup"


class GoogleWeatherError(Exception):
    def __init__(self, friendly_message: str, *, status_code: int | None = None, details: str | None = None) -> None:
        super().__init__(friendly_message)
        self.friendly_message = friendly_message
        self.status_code = status_code
        self.details = details


@dataclass(frozen=True)
class CurrentWeather:
    condition: str
    temperature_degrees: float | None
    feels_like_degrees: float | None
    temperature_unit: str | None
    precipitation_percent: int | None


@dataclass(frozen=True)
class DailyWeather:
    condition: str
    high_degrees: float | None
    low_degrees: float | None
    temperature_unit: str | None
    precipitation_percent: int | None
    uv_index: int | None


def fetch_current_weather(config: dict[str, Any], *, timeout_seconds: int = 15) -> CurrentWeather:
    data = _get_weather_json(
        config,
        url=CURRENT_CONDITIONS_URL,
        route_label="current conditions",
        timeout_seconds=timeout_seconds,
    )

    temperature = _extract_temperature(data, "temperature")
    feels_like = _extract_temperature(data, "feelsLikeTemperature")
    return CurrentWeather(
        condition=_extract_condition(data),
        temperature_degrees=temperature,
        feels_like_degrees=feels_like,
        temperature_unit=_extract_temperature_unit(data, "temperature"),
        precipitation_percent=_extract_precipitation_percent(data),
    )


def fetch_daily_weather(config: dict[str, Any], *, timeout_seconds: int = 15) -> DailyWeather:
    weather_config = config["weather"]
    data = _get_weather_json(
        config,
        url=DAILY_FORECAST_URL,
        route_label="daily forecast",
        timeout_seconds=timeout_seconds,
        extra_params={"days": int(weather_config["daily_days"])},
    )

    forecast_days = data.get("forecastDays")
    if not isinstance(forecast_days, list) or not forecast_days:
        raise GoogleWeatherError("Google Weather API returned no daily forecast for the configured weather location.")

    day = forecast_days[0]
    if not isinstance(day, dict):
        raise GoogleWeatherError("Google Weather API daily forecast response was not in the expected format.")

    daytime = day.get("daytimeForecast")
    if not isinstance(daytime, dict):
        daytime = {}

    high_temperature = _extract_temperature(day, "maxTemperature")
    low_temperature = _extract_temperature(day, "minTemperature")
    return DailyWeather(
        condition=_extract_condition(daytime),
        high_degrees=high_temperature,
        low_degrees=low_temperature,
        temperature_unit=_extract_temperature_unit(day, "maxTemperature")
        or _extract_temperature_unit(day, "minTemperature"),
        precipitation_percent=_extract_precipitation_percent(daytime),
        uv_index=_extract_integer(daytime, "uvIndex"),
    )


def _get_weather_json(
    config: dict[str, Any],
    *,
    url: str,
    route_label: str,
    timeout_seconds: int,
    extra_params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if requests is None:
        raise GoogleWeatherError("The 'requests' package is not installed. Run: pip install -r requirements.txt")

    google_config = config["google"]
    weather_config = config["weather"]
    api_key = google_config.get("api_key")
    if is_placeholder_api_key(api_key):
        raise GoogleWeatherError("Google API key missing. Add it to config.yaml under google.api_key.")

    params: dict[str, Any] = {
        "key": str(api_key),
        "location.latitude": float(weather_config["latitude"]),
        "location.longitude": float(weather_config["longitude"]),
        "unitsSystem": str(weather_config["units_system"]),
    }
    if extra_params:
        params.update(extra_params)

    try:
        response = requests.get(url, params=params, timeout=timeout_seconds)
    except requests.RequestException as exc:
        raise GoogleWeatherError(f"Google Weather API {route_label} request failed: {exc}") from exc

    if response.status_code >= 400:
        message = _extract_error_message(response)
        raise GoogleWeatherError(
            _friendly_http_error(response.status_code, message),
            status_code=response.status_code,
            details=message,
        )

    try:
        data = response.json()
    except ValueError as exc:
        raise GoogleWeatherError(f"Google Weather API returned a non-JSON response for {route_label}.") from exc

    if not isinstance(data, dict):
        raise GoogleWeatherError(f"Google Weather API {route_label} response was not an object.")
    return data


def _extract_condition(data: dict[str, Any]) -> str:
    condition = data.get("weatherCondition")
    if isinstance(condition, dict):
        description = condition.get("description")
        if isinstance(description, dict):
            text = description.get("text")
            if isinstance(text, str) and text.strip():
                return text.strip()
        condition_type = condition.get("type")
        if isinstance(condition_type, str) and condition_type and condition_type != "TYPE_UNSPECIFIED":
            return condition_type.replace("_", " ").title()
    return "Unknown"


def _extract_temperature(data: dict[str, Any], field_name: str) -> float | None:
    temperature = data.get(field_name)
    if not isinstance(temperature, dict):
        return None
    degrees = temperature.get("degrees")
    if isinstance(degrees, bool) or not isinstance(degrees, (int, float)):
        return None
    return float(degrees)


def _extract_temperature_unit(data: dict[str, Any], field_name: str) -> str | None:
    temperature = data.get(field_name)
    if not isinstance(temperature, dict):
        return None
    unit = temperature.get("unit")
    return unit if isinstance(unit, str) and unit else None


def _extract_precipitation_percent(data: dict[str, Any]) -> int | None:
    precipitation = data.get("precipitation")
    if not isinstance(precipitation, dict):
        return None
    probability = precipitation.get("probability")
    if not isinstance(probability, dict):
        return None
    return _extract_integer(probability, "percent")


def _extract_integer(data: dict[str, Any], field_name: str) -> int | None:
    value = data.get(field_name)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return int(round(value))


def _extract_error_message(response: Any) -> str:
    try:
        body = response.json()
    except ValueError:
        return response.text.strip()
    error = body.get("error") if isinstance(body, dict) else None
    if isinstance(error, dict):
        message = error.get("message")
        if isinstance(message, str):
            return message
    return str(body)


def _friendly_http_error(status_code: int, message: str) -> str:
    if status_code in {401, 403}:
        return (
            "Google Weather API authentication, billing, or permission failed. "
            f"Check the API key, Weather API enablement, and billing. Details: {message}"
        )
    if status_code == 429:
        return f"Google Weather API quota was exceeded. Details: {message}"
    return f"Google Weather API returned HTTP {status_code}. Details: {message}"
