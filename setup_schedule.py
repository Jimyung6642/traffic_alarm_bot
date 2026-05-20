from __future__ import annotations

import argparse
import plistlib
import sys
from pathlib import Path
from typing import Any

from config_loader import DEFAULT_CONFIG_PATH, ConfigError, load_config, parse_schedule_times, resolve_config_path, resolve_path


LABEL = "com.commutebot.morning"
PLIST_PATH = Path(__file__).with_name("launchd") / f"{LABEL}.plist"


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a macOS launchd plist from config.yaml schedule times.")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Path to config.yaml")
    args = parser.parse_args()

    try:
        config_path = resolve_config_path(args.config)
        config = load_config(config_path)
        plist = build_plist(config, config_path)
    except ConfigError as exc:
        print(f"[FAIL] {exc}")
        return 1

    PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with PLIST_PATH.open("wb") as handle:
        plistlib.dump(plist, handle, sort_keys=False)

    launch_agent_path = f"~/Library/LaunchAgents/{LABEL}.plist"
    print(f"[OK] wrote {PLIST_PATH}")
    print()
    print("Install with:")
    print("mkdir -p ~/Library/LaunchAgents")
    print(f"cp {PLIST_PATH} {launch_agent_path}")
    print(f"launchctl unload {launch_agent_path} 2>/dev/null")
    print(f"launchctl load {launch_agent_path}")
    print()
    print("Check status with:")
    print("launchctl list | grep commutebot")
    return 0


def build_plist(config: dict[str, Any], config_path: Path) -> dict[str, Any]:
    if not config["schedule"].get("enabled", True):
        raise ConfigError("schedule.enabled is false. Set it to true before generating a launchd plist.")

    times = parse_schedule_times(config["schedule"]["times"])
    project_dir = Path(__file__).resolve().parent
    main_path = project_dir / "main.py"
    log_path = resolve_path(config_path, config["logging"]["log_path"])
    stdout_path = log_path.with_suffix(".stdout.log")
    stderr_path = log_path.with_suffix(".stderr.log")

    return {
        "Label": LABEL,
        "ProgramArguments": [
            sys.executable,
            str(main_path),
            "--config",
            str(config_path),
        ],
        "WorkingDirectory": str(project_dir),
        "StartCalendarInterval": [{"Hour": hour, "Minute": minute} for hour, minute in times],
        "StandardOutPath": str(stdout_path),
        "StandardErrorPath": str(stderr_path),
        "RunAtLoad": False,
    }


if __name__ == "__main__":
    raise SystemExit(main())
