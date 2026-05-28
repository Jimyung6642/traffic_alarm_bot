from __future__ import annotations

import subprocess
import unittest
from unittest.mock import patch

from imessage import IMessageError, check_messages_automation, send_imessage


class IMessageTests(unittest.TestCase):
    def test_check_messages_automation_raises_friendly_timeout(self) -> None:
        with patch("imessage.subprocess.run", side_effect=subprocess.TimeoutExpired(["osascript"], 15)):
            with self.assertRaisesRegex(IMessageError, "Automation permission"):
                check_messages_automation()

    def test_check_messages_automation_raises_friendly_denied_error(self) -> None:
        result = subprocess.CompletedProcess(
            ["osascript"],
            1,
            stdout="",
            stderr="execution error: Not authorized to send Apple events to Messages. (-1743)",
        )

        with patch("imessage.subprocess.run", return_value=result):
            with self.assertRaisesRegex(IMessageError, "automation permission denied"):
                check_messages_automation()

    def test_send_imessage_preflights_and_uses_longer_timeout(self) -> None:
        success = subprocess.CompletedProcess(["osascript"], 0, stdout="", stderr="")

        with patch("imessage.subprocess.run", return_value=success) as run:
            send_imessage(["person@example.com"], "hello", timeout_seconds=90)

        self.assertEqual(run.call_count, 2)
        self.assertEqual(run.call_args_list[0].kwargs["timeout"], 15)
        self.assertEqual(run.call_args_list[1].kwargs["timeout"], 90)

    def test_send_imessage_reports_send_timeout(self) -> None:
        success = subprocess.CompletedProcess(["osascript"], 0, stdout="", stderr="")

        with patch(
            "imessage.subprocess.run",
            side_effect=[success, subprocess.TimeoutExpired(["osascript"], 90)],
        ):
            with self.assertRaisesRegex(IMessageError, "recipient 1: osascript timed out after 90 seconds"):
                send_imessage(["person@example.com"], "hello", timeout_seconds=90)

    def test_send_imessage_redacts_recipient_in_error(self) -> None:
        preflight_success = subprocess.CompletedProcess(["osascript"], 0, stdout="", stderr="")
        send_failure = subprocess.CompletedProcess(
            ["osascript"],
            1,
            stdout="",
            stderr="execution error: Messages got an error.",
        )

        with patch("imessage.subprocess.run", side_effect=[preflight_success, send_failure]):
            with self.assertRaises(IMessageError) as context:
                send_imessage(["person@example.com"], "hello")

        self.assertIn("recipient 1:", str(context.exception))
        self.assertNotIn("person@example.com", str(context.exception))


if __name__ == "__main__":
    unittest.main()
