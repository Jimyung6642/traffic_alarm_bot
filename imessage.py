from __future__ import annotations

import subprocess


class IMessageError(Exception):
    """Raised when Messages.app cannot send one or more iMessages."""


APPLESCRIPT = """
on run argv
    set targetBuddy to item 1 of argv
    set targetMessage to item 2 of argv
    tell application "Messages"
        set targetService to 1st service whose service type = iMessage
        set targetBuddyObject to buddy targetBuddy of targetService
        send targetMessage to targetBuddyObject
    end tell
end run
"""


def send_imessage(recipients: list[str], message: str) -> None:
    unique_recipients = _dedupe_recipients(recipients)
    if not unique_recipients:
        raise IMessageError("No iMessage recipients configured.")

    failures: list[str] = []
    for recipient in unique_recipients:
        try:
            result = subprocess.run(
                ["osascript", "-e", APPLESCRIPT, recipient, message],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
        except FileNotFoundError as exc:
            raise IMessageError("osascript is not available. This bot must run on macOS.") from exc
        except subprocess.TimeoutExpired as exc:
            failures.append(f"{recipient}: osascript timed out while sending")
            continue

        if result.returncode != 0:
            failures.append(f"{recipient}: {_friendly_osascript_error(result.stderr or result.stdout)}")

    if failures:
        raise IMessageError("; ".join(failures))


def _dedupe_recipients(recipients: list[str]) -> list[str]:
    seen: set[str] = set()
    cleaned: list[str] = []
    for recipient in recipients:
        normalized = recipient.strip()
        if normalized and normalized not in seen:
            seen.add(normalized)
            cleaned.append(normalized)
    return cleaned


def _friendly_osascript_error(raw_error: str) -> str:
    error = raw_error.strip()
    lower = error.lower()
    if "-1743" in error or "not authorized" in lower or "not authorised" in lower:
        return (
            "Messages.app automation permission denied. Allow Terminal or Python to control "
            "Messages in System Settings > Privacy & Security > Automation."
        )
    if "application isn't running" in lower or "can't get application" in lower:
        return "Messages.app is unavailable or not running."
    if "can't get service" in lower or "imessage" in lower and "can't get" in lower:
        return "No iMessage service is available. Sign in to Messages.app and enable iMessage."
    return error or "Unknown Messages.app AppleScript error."
