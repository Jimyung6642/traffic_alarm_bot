from __future__ import annotations

import argparse
import os
import plistlib
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

from config_loader import DEFAULT_CONFIG_PATH, ConfigError, load_config, parse_schedule_times, resolve_config_path


LABEL = "com.commutebot.morning"
PROJECT_DIR = Path(__file__).resolve().parent
PLIST_PATH = PROJECT_DIR / "launchd" / f"{LABEL}.plist"
APP_SUPPORT_DIR = Path.home() / "Library" / "Application Support" / "CommuteBot"
LAUNCH_AGENTS_DIR = Path.home() / "Library" / "LaunchAgents"
LOG_DIR = Path.home() / "Library" / "Logs" / "CommuteBot"
WRAPPER_PATH = APP_SUPPORT_DIR / "run_commutebot.sh"
INSTALLED_PLIST_PATH = LAUNCH_AGENTS_DIR / f"{LABEL}.plist"
STDOUT_PATH = LOG_DIR / "morning.stdout.log"
STDERR_PATH = LOG_DIR / "morning.stderr.log"


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate or install the macOS launchd schedule.")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Path to config.yaml")
    parser.add_argument(
        "--install",
        action="store_true",
        help="Install the LaunchAgent, wrapper script, and reload the launchd job.",
    )
    parser.add_argument(
        "--no-reload",
        action="store_true",
        help="With --install, write files without bootout/bootstrap.",
    )
    args = parser.parse_args()

    try:
        config_path = resolve_config_path(args.config)
        config = load_config(config_path)
        plist = build_plist(config, config_path)
        wrapper_script = build_wrapper_script(config_path)
    except ConfigError as exc:
        print(f"[FAIL] {exc}")
        return 1

    PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with PLIST_PATH.open("wb") as handle:
        plistlib.dump(plist, handle, sort_keys=False)

    print(f"[OK] wrote {PLIST_PATH}")

    if args.install:
        try:
            install_launch_agent(plist, wrapper_script, reload_job=not args.no_reload)
        except (OSError, subprocess.CalledProcessError) as exc:
            print(f"[FAIL] could not install LaunchAgent: {exc}")
            return 1
        return 0

    print()
    print("Install with:")
    print(f"{shlex.quote(sys.executable)} {shlex.quote(str(Path(__file__).resolve()))} --config {shlex.quote(str(config_path))} --install")
    print()
    print("Check status with:")
    print(f"launchctl print gui/$(id -u)/{LABEL}")
    return 0


def build_plist(
    config: dict[str, Any],
    config_path: Path,
    *,
    wrapper_path: Path = WRAPPER_PATH,
    stdout_path: Path = STDOUT_PATH,
    stderr_path: Path = STDERR_PATH,
) -> dict[str, Any]:
    if not config["schedule"].get("enabled", True):
        raise ConfigError("schedule.enabled is false. Set it to true before generating a launchd plist.")

    times = parse_schedule_times(config["schedule"]["times"])

    return {
        "Label": LABEL,
        "ProgramArguments": [
            "/bin/zsh",
            str(wrapper_path),
        ],
        "WorkingDirectory": "/private/tmp",
        "StartCalendarInterval": [{"Hour": hour, "Minute": minute} for hour, minute in times],
        "StandardOutPath": str(stdout_path),
        "StandardErrorPath": str(stderr_path),
        "RunAtLoad": False,
    }


def build_wrapper_script(
    config_path: Path,
    *,
    python_path: str | Path = sys.executable,
    project_dir: Path = PROJECT_DIR,
) -> str:
    main_path = project_dir / "main.py"
    command = " ".join(
        (
            shlex.quote(str(python_path)),
            "-B",
            shlex.quote(str(main_path)),
            "--config",
            shlex.quote(str(config_path)),
            '"$@"',
        )
    )
    return f"#!/bin/zsh\nset -euo pipefail\ncd /private/tmp\nexec {command}\n"


def install_launch_agent(plist: dict[str, Any], wrapper_script: str, *, reload_job: bool = True) -> None:
    APP_SUPPORT_DIR.mkdir(parents=True, exist_ok=True)
    LAUNCH_AGENTS_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    WRAPPER_PATH.write_text(wrapper_script, encoding="utf-8")
    WRAPPER_PATH.chmod(0o755)
    with INSTALLED_PLIST_PATH.open("wb") as handle:
        plistlib.dump(plist, handle, sort_keys=False)
    INSTALLED_PLIST_PATH.chmod(0o644)

    for path in (WRAPPER_PATH, INSTALLED_PLIST_PATH):
        remove_macos_download_attrs(path)

    print(f"[OK] installed wrapper {WRAPPER_PATH}")
    print(f"[OK] installed plist {INSTALLED_PLIST_PATH}")

    if not reload_job:
        return

    user_domain = f"gui/{os.getuid()}"
    subprocess.run(
        ["launchctl", "bootout", f"{user_domain}/{LABEL}"],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    subprocess.run(["launchctl", "bootstrap", user_domain, str(INSTALLED_PLIST_PATH)], check=True)
    print(f"[OK] reloaded {user_domain}/{LABEL}")


def remove_macos_download_attrs(path: Path) -> None:
    for attr in ("com.apple.provenance", "com.apple.quarantine"):
        subprocess.run(
            ["/usr/bin/xattr", "-d", attr, str(path)],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


if __name__ == "__main__":
    raise SystemExit(main())
