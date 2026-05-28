from __future__ import annotations

import subprocess


class IMessageError(Exception):
    """Raised when Messages.app cannot send one or more iMessages."""


DEFAULT_PREFLIGHT_TIMEOUT_SECONDS = 15
DEFAULT_SEND_TIMEOUT_SECONDS = 120
PREFLIGHT_APPLESCRIPT = 'tell application "Messages" to count of services'
APPLESCRIPT = """
on run argv
    set targetBuddy to item 1 of argv
    set targetMessage to item 2 of argv
    tell application "Messages"
        set targetService to missing value
        repeat with candidateService in services
            try
                if (enabled of candidateService is true) and ((service type of candidateService as text) is "iMessage") then
                    set targetService to candidateService
                    exit repeat
                end if
            end try
        end repeat
        if targetService is missing value then
            error "No enabled iMessage service is available. Sign in to Messages.app and enable iMessage."
        end if
        set targetBuddyObject to buddy targetBuddy of targetService
        send targetMessage to targetBuddyObject
    end tell
end run
"""


def check_messages_automation(timeout_seconds: int = DEFAULT_PREFLIGHT_TIMEOUT_SECONDS) -> None:
    try:
        result = subprocess.run(
            ["osascript", "-e", PREFLIGHT_APPLESCRIPT],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except FileNotFoundError as exc:
        raise IMessageError("osascript is not available. This bot must run on macOS.") from exc
    except subprocess.TimeoutExpired as exc:
        raise IMessageError(
            "Messages.app Automation permission did not complete. If macOS is asking for permission, "
            "allow python3.13 to control Messages, then run setup_check.py --check-imessage."
        ) from exc

    if result.returncode != 0:
        raise IMessageError(_friendly_osascript_error(result.stderr or result.stdout))


def send_imessage(
    recipients: list[str],
    message: str,
    *,
    timeout_seconds: int = DEFAULT_SEND_TIMEOUT_SECONDS,
) -> None:
    unique_recipients = _dedupe_recipients(recipients)
    if not unique_recipients:
        raise IMessageError("No iMessage recipients configured.")

    check_messages_automation()

    failures: list[str] = []
    for index, recipient in enumerate(unique_recipients, start=1):
        recipient_label = f"recipient {index}"
        try:
            result = subprocess.run(
                ["osascript", "-e", APPLESCRIPT, recipient, message],
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
                check=False,
            )
        except FileNotFoundError as exc:
            raise IMessageError("osascript is not available. This bot must run on macOS.") from exc
        except subprocess.TimeoutExpired as exc:
            failures.append(
                f"{recipient_label}: osascript timed out after {timeout_seconds} seconds while sending"
            )
            continue

        if result.returncode != 0:
            failures.append(f"{recipient_label}: {_friendly_osascript_error(result.stderr or result.stdout)}")

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
