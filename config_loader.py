from __future__ import annotations

import re
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover - exercised only before dependencies exist
    yaml = None  # type: ignore[assignment]


DEFAULT_CONFIG_PATH = Path(__file__).with_name("config.yaml")
SCHEDULE_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


class ConfigError(Exception):
    """Raised when config.yaml cannot be loaded or is structurally invalid."""


def load_config(config_path: str | Path = DEFAULT_CONFIG_PATH) -> dict[str, Any]:
    path = Path(config_path).expanduser()
    if yaml is None:
        raise ConfigError("PyYAML is not installed. Run: pip install -r requirements.txt")
    if not path.exists():
        raise ConfigError(f"config.yaml not found at {path}")

    try:
        with path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
    except OSError as exc:
        raise ConfigError(f"Could not read config.yaml: {exc}") from exc
    except yaml.YAMLError as exc:
        raise ConfigError(f"config.yaml is not valid YAML: {exc}") from exc

    if not isinstance(data, dict):
        raise ConfigError("config.yaml must contain a top-level mapping")
    return data


def resolve_config_path(config_path: str | Path) -> Path:
    return Path(config_path).expanduser().resolve()


def resolve_path(config_path: str | Path, raw_path: str) -> Path:
    path = Path(raw_path).expanduser()
    if path.is_absolute():
        return path
    return resolve_config_path(config_path).parent / path


def get_section(config: dict[str, Any], name: str) -> dict[str, Any]:
    section = config.get(name)
    if not isinstance(section, dict):
        raise ConfigError(f"config.yaml section '{name}' must be a mapping")
    return section


def parse_schedule_times(times: Any) -> list[tuple[int, int]]:
    if not isinstance(times, list) or not times:
        raise ConfigError("schedule.times must be a non-empty list of HH:MM strings")

    parsed: list[tuple[int, int]] = []
    seen: set[str] = set()
    for item in times:
        if not isinstance(item, str):
            raise ConfigError("schedule.times entries must be strings like '06:25'")
        match = SCHEDULE_RE.match(item)
        if not match:
            raise ConfigError(f"Invalid schedule time '{item}'. Use 24-hour HH:MM format.")
        if item in seen:
            raise ConfigError(f"Duplicate schedule time '{item}'")
        seen.add(item)
        parsed.append((int(match.group(1)), int(match.group(2))))
    return parsed


def is_placeholder_api_key(api_key: Any) -> bool:
    if not isinstance(api_key, str) or not api_key.strip():
        return True
    normalized = api_key.strip().upper()
    placeholders = ("PUT_API_KEY_HERE", "YOUR_API_KEY", "REPLACE_ME", "PLACEHOLDER")
    return normalized in placeholders or normalized.startswith("PUT_") or "XXXXX" in normalized


def validate_config(config: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required_sections = (
        "google",
        "commute",
        "traffic",
        "imessage",
        "message",
        "schedule",
        "storage",
        "logging",
    )
    for section_name in required_sections:
        if not isinstance(config.get(section_name), dict):
            errors.append(f"Missing or invalid section: {section_name}")

    if errors:
        return errors

    google = get_section(config, "google")
    commute = get_section(config, "commute")
    traffic = get_section(config, "traffic")
    imessage = get_section(config, "imessage")
    message = get_section(config, "message")
    schedule = get_section(config, "schedule")
    storage = get_section(config, "storage")
    logging_config = get_section(config, "logging")

    _require_string(errors, google, "routes_api_url", "google.routes_api_url")
    _require_string(errors, commute, "origin_address", "commute.origin_address")
    _require_string(errors, commute, "destination_address", "commute.destination_address")
    _require_string(errors, commute, "transit_origin_address", "commute.transit_origin_address")
    _require_string(errors, commute, "transit_destination_address", "commute.transit_destination_address")
    _require_string(errors, commute, "timezone", "commute.timezone")
    _require_string(errors, message, "template", "message.template")
    _require_string(errors, storage, "sqlite_path", "storage.sqlite_path")
    _require_string(errors, logging_config, "log_path", "logging.log_path")

    for key in (
        "expected_shuttle_drive_min",
        "estimated_transit_min_low",
        "estimated_transit_min_high",
        "warning_delay_min",
        "severe_delay_min",
        "transit_advantage_buffer_min",
    ):
        value = traffic.get(key)
        if not isinstance(value, (int, float)) or value < 0:
            errors.append(f"traffic.{key} must be a non-negative number")

    if isinstance(traffic.get("estimated_transit_min_low"), (int, float)) and isinstance(
        traffic.get("estimated_transit_min_high"), (int, float)
    ):
        if traffic["estimated_transit_min_low"] > traffic["estimated_transit_min_high"]:
            errors.append("traffic.estimated_transit_min_low must be <= estimated_transit_min_high")

    if isinstance(traffic.get("warning_delay_min"), (int, float)) and isinstance(
        traffic.get("severe_delay_min"), (int, float)
    ):
        if traffic["warning_delay_min"] >= traffic["severe_delay_min"]:
            errors.append("traffic.warning_delay_min must be less than traffic.severe_delay_min")

    if not isinstance(imessage.get("send_enabled"), bool):
        errors.append("imessage.send_enabled must be true or false")
    if not isinstance(imessage.get("dry_run"), bool):
        errors.append("imessage.dry_run must be true or false")
    recipients = imessage.get("recipients")
    if not isinstance(recipients, list) or not all(isinstance(item, str) and item.strip() for item in recipients):
        errors.append("imessage.recipients must be a non-empty list of phone numbers or Apple IDs")

    if not isinstance(schedule.get("enabled"), bool):
        errors.append("schedule.enabled must be true or false")
    try:
        parse_schedule_times(schedule.get("times"))
    except ConfigError as exc:
        errors.append(str(exc))

    retention_days = storage.get("retention_days")
    if not isinstance(retention_days, int) or retention_days < 1:
        errors.append("storage.retention_days must be an integer >= 1")

    log_level = logging_config.get("log_level")
    if not isinstance(log_level, str) or log_level.upper() not in {
        "DEBUG",
        "INFO",
        "WARNING",
        "ERROR",
        "CRITICAL",
    }:
        errors.append("logging.log_level must be DEBUG, INFO, WARNING, ERROR, or CRITICAL")

    return errors


def _require_string(errors: list[str], section: dict[str, Any], key: str, label: str) -> None:
    value = section.get(key)
    if not isinstance(value, str) or not value.strip():
        errors.append(f"{label} must be a non-empty string")
