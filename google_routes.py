from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

try:
    import requests
except ImportError:  # pragma: no cover - exercised only before dependencies exist
    requests = None  # type: ignore[assignment]

from config_loader import is_placeholder_api_key


DURATION_RE = re.compile(r"^(\d+(?:\.\d+)?)s$")
FIELD_MASK = "routes.duration,routes.staticDuration,routes.distanceMeters"


class GoogleRoutesError(Exception):
    def __init__(self, friendly_message: str, *, status_code: int | None = None, details: str | None = None) -> None:
        super().__init__(friendly_message)
        self.friendly_message = friendly_message
        self.status_code = status_code
        self.details = details


@dataclass(frozen=True)
class RouteDuration:
    duration_min: float
    static_duration_min: float | None
    distance_meters: int | None


def parse_duration_to_minutes(raw_duration: str) -> float:
    match = DURATION_RE.match(raw_duration)
    if not match:
        raise ValueError(f"Unsupported Google duration value: {raw_duration!r}")
    return float(match.group(1)) / 60.0


def fetch_traffic_duration(config: dict[str, Any], *, timeout_seconds: int = 15) -> RouteDuration:
    if requests is None:
        raise GoogleRoutesError("The 'requests' package is not installed. Run: pip install -r requirements.txt")

    google_config = config["google"]
    commute_config = config["commute"]
    api_key = google_config.get("api_key")
    if is_placeholder_api_key(api_key):
        raise GoogleRoutesError("Google API key missing. Add it to config.yaml under google.api_key.")

    payload = {
        "origin": {"address": commute_config["origin_address"]},
        "destination": {"address": commute_config["destination_address"]},
        "travelMode": "DRIVE",
        "routingPreference": "TRAFFIC_AWARE",
    }
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": str(api_key),
        "X-Goog-FieldMask": FIELD_MASK,
    }

    try:
        response = requests.post(
            google_config["routes_api_url"],
            json=payload,
            headers=headers,
            timeout=timeout_seconds,
        )
    except requests.RequestException as exc:
        raise GoogleRoutesError(f"Google Routes API request failed: {exc}") from exc

    if response.status_code >= 400:
        message = _extract_error_message(response)
        raise GoogleRoutesError(
            _friendly_http_error(response.status_code, message),
            status_code=response.status_code,
            details=message,
        )

    try:
        data = response.json()
    except ValueError as exc:
        raise GoogleRoutesError("Google Routes API returned a non-JSON response.") from exc

    routes = data.get("routes")
    if not isinstance(routes, list) or not routes:
        raise GoogleRoutesError("Google Routes API returned no routes for the configured commute.")

    route = routes[0]
    if not isinstance(route, dict) or not isinstance(route.get("duration"), str):
        raise GoogleRoutesError("Google Routes API response did not include routes.duration.")

    try:
        duration_min = parse_duration_to_minutes(route["duration"])
        static_duration_min = (
            parse_duration_to_minutes(route["staticDuration"])
            if isinstance(route.get("staticDuration"), str)
            else None
        )
    except ValueError as exc:
        raise GoogleRoutesError(str(exc)) from exc

    distance_meters = route.get("distanceMeters")
    if not isinstance(distance_meters, int):
        distance_meters = None

    return RouteDuration(
        duration_min=duration_min,
        static_duration_min=static_duration_min,
        distance_meters=distance_meters,
    )


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
            "Google Routes API authentication, billing, or permission failed. "
            f"Check the API key, Routes API enablement, and billing. Details: {message}"
        )
    if status_code == 429:
        return f"Google Routes API quota was exceeded. Details: {message}"
    return f"Google Routes API returned HTTP {status_code}. Details: {message}"
