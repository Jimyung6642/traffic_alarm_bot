from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from config_loader import (
    DEFAULT_CONFIG_PATH,
    ConfigError,
    is_placeholder_api_key,
    load_config,
    parse_schedule_times,
    resolve_config_path,
    validate_config,
)
from google_routes import GoogleRoutesError, fetch_traffic_duration
from imessage import IMessageError, send_imessage


def main() -> int:
    parser = argparse.ArgumentParser(description="Run CommuteBot setup checks.")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Path to config.yaml")
    parser.add_argument("--check-config", action="store_true", help="Validate config.yaml")
    parser.add_argument("--check-google", action="store_true", help="Make one Google Routes API test request")
    parser.add_argument("--test-imessage", action="store_true", help="Send one test iMessage if real sending is enabled")
    parser.add_argument("--recipient", help="Recipient for --test-imessage")
    args = parser.parse_args()

    if not (args.check_config or args.check_google or args.test_imessage):
        parser.print_help()
        return 2

    exit_code = 0
    if args.check_config:
        exit_code = max(exit_code, check_config(args.config))
    if args.check_google:
        exit_code = max(exit_code, check_google(args.config))
    if args.test_imessage:
        exit_code = max(exit_code, test_imessage(args.config, args.recipient))
    return exit_code


def check_config(config_path: str | Path) -> int:
    path = resolve_config_path(config_path)
    if not path.exists():
        print(f"[FAIL] config.yaml not found at {path}")
        return 1
    print("[OK] config.yaml found")

    try:
        config = load_config(path)
    except ConfigError as exc:
        print(f"[FAIL] {exc}")
        return 1

    errors = validate_config(config)
    if errors:
        for error in errors:
            print(f"[FAIL] {error}")
        return 1

    try:
        parse_schedule_times(config["schedule"]["times"])
        ZoneInfo(config["commute"]["timezone"])
    except (ConfigError, ZoneInfoNotFoundError) as exc:
        print(f"[FAIL] {exc}")
        return 1

    print(f"[OK] schedule has {len(config['schedule']['times'])} daily time(s)")
    print(f"[OK] timezone is {config['commute']['timezone']}")
    if config["imessage"]["dry_run"] or not config["imessage"]["send_enabled"]:
        print("[OK] safe sending defaults are active")
    else:
        print("[OK] real iMessage sending is enabled")
    return 0


def check_google(config_path: str | Path) -> int:
    try:
        config = load_config(config_path)
    except ConfigError as exc:
        print(f"[FAIL] {exc}")
        return 1

    if is_placeholder_api_key(config.get("google", {}).get("api_key")):
        print("[FAIL] Google API key missing. Add it to config.yaml under google.api_key.")
        return 1

    print("[OK] Google API key found")
    try:
        route = fetch_traffic_duration(config)
    except GoogleRoutesError as exc:
        print(f"[FAIL] {exc.friendly_message}")
        return 1

    print(f"[OK] Google Routes API returned traffic duration: {round(route.duration_min)} min")
    return 0


def test_imessage(config_path: str | Path, recipient: str | None) -> int:
    if not recipient:
        print('[FAIL] --recipient is required for --test-imessage, for example: --recipient "+1XXXXXXXXXX"')
        return 1

    try:
        config = load_config(config_path)
    except ConfigError as exc:
        print(f"[FAIL] {exc}")
        return 1

    if not config.get("imessage", {}).get("send_enabled", False):
        print("[FAIL] send_enabled is false, real iMessage sending disabled")
        return 1
    if config.get("imessage", {}).get("dry_run", True):
        print("[FAIL] dry_run is true, real iMessage sending disabled")
        return 1

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    try:
        send_imessage([recipient], f"CommuteBot setup test - {timestamp}")
    except IMessageError as exc:
        print(f"[FAIL] {exc}")
        return 1

    print(f"[OK] test iMessage sent to {recipient}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
