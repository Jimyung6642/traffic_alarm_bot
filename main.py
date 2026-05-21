from __future__ import annotations

import argparse
import logging
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from config_loader import (
    DEFAULT_CONFIG_PATH,
    ConfigError,
    load_config,
    parse_schedule_times,
    resolve_config_path,
    resolve_path,
    validate_config,
)
from decision import DecisionResult, make_decision
from google_routes import GoogleRoutesError, RouteDuration, fetch_traffic_duration, fetch_transit_duration
from google_weather import (
    CurrentWeather,
    DailyWeather,
    GoogleWeatherError,
    fetch_current_weather,
    fetch_daily_weather,
)
from imessage import IMessageError, send_imessage
from reason_messages import compose_reason
from storage import cleanup_old_records, has_successful_message_for_run_key, init_db, record_run


FALLBACK_RECOMMENDATION = "Traffic check unavailable"
FALLBACK_MESSAGE = (
    "CommuteBot could not check traffic today. Please manually check traffic before "
    "choosing shuttle vs NJ Transit."
)
WEATHER_UNAVAILABLE = "Unavailable"
WEATHER_VALUE_UNAVAILABLE = "N/A"


def main() -> int:
    parser = argparse.ArgumentParser(description="Check commute traffic and send an iMessage recommendation.")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Path to config.yaml")
    parser.add_argument("--dry-run", action="store_true", help="Print the message instead of sending iMessage")
    parser.add_argument("--no-send", action="store_true", help="Disable real iMessage sending for this run")
    args = parser.parse_args()

    return run_once(config_path=args.config, force_dry_run=args.dry_run, force_no_send=args.no_send)


def run_once(*, config_path: str | Path, force_dry_run: bool = False, force_no_send: bool = False) -> int:
    try:
        resolved_config_path = resolve_config_path(config_path)
        config = load_config(resolved_config_path)
        config_errors = validate_config(config)
        if config_errors:
            for error in config_errors:
                print(f"[FAIL] {error}")
            return 2
        _configure_logging(config, resolved_config_path)
        now = _current_time(config)
    except (ConfigError, ZoneInfoNotFoundError) as exc:
        print(f"[FAIL] {exc}")
        return 2

    logger = logging.getLogger(__name__)
    storage_path = resolve_path(resolved_config_path, config["storage"]["sqlite_path"])
    init_db(storage_path)

    run_key = _build_run_key(now, config)
    effective_send_enabled = bool(config["imessage"].get("send_enabled", False)) and not force_no_send
    effective_dry_run = bool(config["imessage"].get("dry_run", True)) or force_dry_run or not effective_send_enabled

    if effective_send_enabled and not effective_dry_run and has_successful_message_for_run_key(storage_path, run_key):
        message = f"Skipped duplicate scheduled run {run_key}; message already sent."
        print(message)
        logger.info(message)
        _record_and_cleanup(
            storage_path=storage_path,
            config=config,
            now=now,
            run_key=run_key,
            dry_run=effective_dry_run,
            send_enabled=effective_send_enabled,
            message_sent=False,
            error_message=message,
        )
        return 0

    route: RouteDuration | None = None
    transit_route: RouteDuration | None = None
    current_weather: CurrentWeather | None = None
    daily_weather: DailyWeather | None = None
    weather_error: str | None = None
    decision: DecisionResult | None = None
    error_message: str | None = None

    try:
        route = fetch_traffic_duration(config)
        transit_route = fetch_transit_duration(config)
        traffic = config["traffic"]
        decision = make_decision(
            current_drive_min=route.duration_min,
            baseline_min=float(traffic["expected_shuttle_drive_min"]),
            transit_min_low=float(traffic["estimated_transit_min_low"]),
            transit_min_high=float(traffic["estimated_transit_min_high"]),
            warning_delay_min=float(traffic["warning_delay_min"]),
            severe_delay_min=float(traffic["severe_delay_min"]),
            transit_advantage_buffer_min=float(traffic["transit_advantage_buffer_min"]),
        )
        if _weather_enabled(config):
            try:
                current_weather = fetch_current_weather(config)
                daily_weather = fetch_daily_weather(config)
            except GoogleWeatherError as exc:
                weather_error = exc.friendly_message
                logger.warning("Google Weather check failed: %s", exc.friendly_message)
                if exc.details:
                    logger.warning("Google Weather details: %s", exc.details)
        message = _render_configured_message(
            config,
            now=now,
            route=route,
            transit_route=transit_route,
            current_weather=current_weather,
            daily_weather=daily_weather,
            weather_error=weather_error,
            decision=decision,
        )
    except GoogleRoutesError as exc:
        error_message = exc.friendly_message
        logger.error("Google Routes check failed: %s", exc.friendly_message)
        if exc.details:
            logger.error("Google Routes details: %s", exc.details)
        message = _fallback_message(config, now=now, reason=exc.friendly_message)
    except KeyError as exc:
        error_message = f"Message template uses an unknown variable: {exc}"
        logger.error(error_message)
        message = _fallback_message(config, now=now, reason=error_message)

    message_sent = False
    try:
        if effective_dry_run:
            print(message)
            logger.info("Dry run or sending disabled; iMessage was not sent.")
        else:
            send_imessage(config["imessage"]["recipients"], message)
            message_sent = True
            logger.info("iMessage sent to %d recipient(s).", len(config["imessage"]["recipients"]))
    except IMessageError as exc:
        error_message = str(exc)
        logger.error("iMessage send failed: %s", exc)
        print(message)

    _record_and_cleanup(
        storage_path=storage_path,
        config=config,
        now=now,
        run_key=run_key,
        route=route,
        transit_route=transit_route,
        decision=decision,
        dry_run=effective_dry_run,
        send_enabled=effective_send_enabled,
        message_sent=message_sent,
        error_message=error_message,
    )
    return 0


def _configure_logging(config: dict[str, Any], config_path: Path) -> None:
    log_path = resolve_path(config_path, config["logging"]["log_path"])
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_level = getattr(logging, config["logging"]["log_level"].upper(), logging.INFO)
    logging.basicConfig(
        filename=log_path,
        level=log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        force=True,
    )


def _current_time(config: dict[str, Any]) -> datetime:
    timezone = ZoneInfo(config["commute"]["timezone"])
    return datetime.now(timezone)


def _build_run_key(now: datetime, config: dict[str, Any]) -> str:
    try:
        schedule_times = parse_schedule_times(config["schedule"]["times"])
    except ConfigError:
        return f"manual:{now.strftime('%Y%m%dT%H%M')}"

    nearest_label = None
    nearest_seconds = None
    for hour, minute in schedule_times:
        scheduled = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        diff_seconds = abs((now - scheduled).total_seconds())
        if nearest_seconds is None or diff_seconds < nearest_seconds:
            nearest_seconds = diff_seconds
            nearest_label = f"{hour:02d}:{minute:02d}"

    if nearest_label is not None and nearest_seconds is not None and nearest_seconds <= 30 * 60:
        return f"scheduled:{now.date().isoformat()}:{nearest_label}"
    return f"manual:{now.strftime('%Y%m%dT%H%M')}"


def _render_configured_message(
    config: dict[str, Any],
    *,
    now: datetime,
    route: RouteDuration,
    transit_route: RouteDuration,
    decision: DecisionResult,
    current_weather: CurrentWeather | None = None,
    daily_weather: DailyWeather | None = None,
    weather_error: str | None = None,
) -> str:
    context = _message_context(
        config,
        now=now,
        route=route,
        transit_route=transit_route,
        decision=decision,
        current_weather=current_weather,
        daily_weather=daily_weather,
        weather_error=weather_error,
    )
    return config["message"]["template"].format(**context)


def _message_context(
    config: dict[str, Any],
    *,
    now: datetime,
    route: RouteDuration,
    transit_route: RouteDuration,
    decision: DecisionResult,
    current_weather: CurrentWeather | None = None,
    daily_weather: DailyWeather | None = None,
    weather_error: str | None = None,
) -> dict[str, str]:
    traffic = config["traffic"]
    delay_min = decision.delay_min
    context = {
        "current_time": now.strftime("%Y-%m-%d %H:%M %Z"),
        "recommendation": decision.recommendation,
        "current_drive_min": _format_minutes(route.duration_min),
        "current_transit_min": _format_minutes(transit_route.duration_min),
        "baseline_min": _format_minutes(float(traffic["expected_shuttle_drive_min"])),
        "delay_min": _format_minutes(delay_min),
        "delay_min_signed": _format_signed_minutes(delay_min),
        "transit_min_low": _format_minutes(float(traffic["estimated_transit_min_low"])),
        "transit_min_high": _format_minutes(float(traffic["estimated_transit_min_high"])),
        "reason": compose_reason(
            decision=decision,
            now=now,
            current_weather=current_weather,
            daily_weather=daily_weather,
        ),
        "traffic_reason": decision.reason,
        "origin_address": config["commute"]["origin_address"],
        "destination_address": config["commute"]["destination_address"],
        "transit_origin_address": config["commute"]["transit_origin_address"],
        "transit_destination_address": config["commute"]["transit_destination_address"],
    }
    context.update(
        _weather_message_context(
            config,
            current_weather=current_weather,
            daily_weather=daily_weather,
            weather_error=weather_error,
        )
    )
    return context


def _fallback_message(config: dict[str, Any], *, now: datetime, reason: str) -> str:
    return (
        f"CommuteBot - {now.strftime('%Y-%m-%d %H:%M %Z')}\n\n"
        f"Recommendation: {FALLBACK_RECOMMENDATION}\n\n"
        f"{FALLBACK_MESSAGE}\n\n"
        f"Reason: {reason}"
    )


def _format_minutes(value: float) -> str:
    return str(int(round(value)))


def _format_signed_minutes(value: float) -> str:
    rounded = int(round(value))
    return f"+{rounded}" if rounded > 0 else str(rounded)


def _weather_enabled(config: dict[str, Any]) -> bool:
    weather = config.get("weather")
    return isinstance(weather, dict) and bool(weather.get("enabled", False))


def _weather_message_context(
    config: dict[str, Any],
    *,
    current_weather: CurrentWeather | None,
    daily_weather: DailyWeather | None,
    weather_error: str | None,
) -> dict[str, str]:
    weather_config = config.get("weather")
    weather_location = config["commute"]["origin_address"]
    if isinstance(weather_config, dict):
        raw_label = weather_config.get("location_label")
        if isinstance(raw_label, str) and raw_label.strip():
            weather_location = raw_label.strip()

    if current_weather is None:
        current_weather_fields = {
            "current_weather_summary": WEATHER_UNAVAILABLE,
            "current_weather_condition": WEATHER_UNAVAILABLE,
            "current_temp_f": WEATHER_VALUE_UNAVAILABLE,
            "current_feels_like_f": WEATHER_VALUE_UNAVAILABLE,
            "current_precip_percent": WEATHER_VALUE_UNAVAILABLE,
        }
    else:
        current_weather_fields = {
            "current_weather_summary": _format_current_weather_summary(current_weather),
            "current_weather_condition": current_weather.condition,
            "current_temp_f": _format_weather_number(current_weather.temperature_degrees),
            "current_feels_like_f": _format_weather_number(current_weather.feels_like_degrees),
            "current_precip_percent": _format_weather_number(current_weather.precipitation_percent),
        }

    if daily_weather is None:
        daily_weather_fields = {
            "daily_weather_summary": WEATHER_UNAVAILABLE,
            "daily_weather_condition": WEATHER_UNAVAILABLE,
            "daily_high_f": WEATHER_VALUE_UNAVAILABLE,
            "daily_low_f": WEATHER_VALUE_UNAVAILABLE,
            "daily_precip_percent": WEATHER_VALUE_UNAVAILABLE,
            "daily_uv_index": WEATHER_VALUE_UNAVAILABLE,
        }
    else:
        daily_weather_fields = {
            "daily_weather_summary": _format_daily_weather_summary(daily_weather),
            "daily_weather_condition": daily_weather.condition,
            "daily_high_f": _format_weather_number(daily_weather.high_degrees),
            "daily_low_f": _format_weather_number(daily_weather.low_degrees),
            "daily_precip_percent": _format_weather_number(daily_weather.precipitation_percent),
            "daily_uv_index": _format_weather_number(daily_weather.uv_index),
        }

    return {
        "weather_location": weather_location,
        "weather_error": weather_error or "",
        **current_weather_fields,
        **daily_weather_fields,
    }


def _format_current_weather_summary(weather: CurrentWeather) -> str:
    temperature = _format_temperature(weather.temperature_degrees, weather.temperature_unit)
    feels_like = _format_temperature(weather.feels_like_degrees, weather.temperature_unit)
    precipitation = _format_percent(weather.precipitation_percent)
    return f"{weather.condition}, {temperature} (feels like {feels_like}), precip {precipitation}"


def _format_daily_weather_summary(weather: DailyWeather) -> str:
    high = _format_temperature(weather.high_degrees, weather.temperature_unit)
    low = _format_temperature(weather.low_degrees, weather.temperature_unit)
    precipitation = _format_percent(weather.precipitation_percent)
    uv_index = _format_weather_number(weather.uv_index)
    return f"{weather.condition}, high {high} / low {low}, precip {precipitation}, UV {uv_index}"


def _format_temperature(value: float | None, unit: str | None) -> str:
    if value is None:
        return WEATHER_VALUE_UNAVAILABLE
    unit_label = _temperature_unit_label(unit)
    return f"{_format_weather_number(value)} {unit_label}" if unit_label else _format_weather_number(value)


def _temperature_unit_label(unit: str | None) -> str:
    if unit == "FAHRENHEIT":
        return "F"
    if unit == "CELSIUS":
        return "C"
    return ""


def _format_percent(value: int | None) -> str:
    if value is None:
        return WEATHER_VALUE_UNAVAILABLE
    return f"{_format_weather_number(value)}%"


def _format_weather_number(value: float | int | None) -> str:
    if value is None:
        return WEATHER_VALUE_UNAVAILABLE
    return str(int(round(value)))


def _record_and_cleanup(
    *,
    storage_path: Path,
    config: dict[str, Any],
    now: datetime,
    run_key: str,
    dry_run: bool,
    send_enabled: bool,
    message_sent: bool,
    route: RouteDuration | None = None,
    transit_route: RouteDuration | None = None,
    decision: DecisionResult | None = None,
    error_message: str | None = None,
) -> None:
    traffic = config["traffic"]
    baseline_min = float(traffic["expected_shuttle_drive_min"])
    delay_min = decision.delay_min if decision else None
    record_run(
        storage_path,
        run_key=run_key,
        timestamp=now.isoformat(timespec="seconds"),
        origin_address=config["commute"]["origin_address"],
        destination_address=config["commute"]["destination_address"],
        transit_origin_address=config["commute"]["transit_origin_address"],
        transit_destination_address=config["commute"]["transit_destination_address"],
        current_drive_min=route.duration_min if route else None,
        current_transit_min=transit_route.duration_min if transit_route else None,
        baseline_min=baseline_min,
        delay_min=delay_min,
        estimated_transit_min_low=float(traffic["estimated_transit_min_low"]),
        estimated_transit_min_high=float(traffic["estimated_transit_min_high"]),
        recommendation=decision.recommendation if decision else FALLBACK_RECOMMENDATION,
        reason=decision.reason if decision else None,
        dry_run=dry_run,
        send_enabled=send_enabled,
        message_sent=message_sent,
        error_message=error_message,
    )
    cleanup_old_records(
        storage_path,
        retention_days=int(config["storage"]["retention_days"]),
        now=now,
    )


if __name__ == "__main__":
    raise SystemExit(main())
