from __future__ import annotations

import unittest

from config_loader import ConfigError, is_placeholder_api_key, parse_schedule_times, validate_config


class ConfigLoaderTests(unittest.TestCase):
    def test_parse_schedule_times(self) -> None:
        self.assertEqual(parse_schedule_times(["06:00", "18:45"]), [(6, 0), (18, 45)])

    def test_parse_schedule_rejects_invalid_time(self) -> None:
        with self.assertRaises(ConfigError):
            parse_schedule_times(["6:00"])

    def test_placeholder_api_key_detection(self) -> None:
        self.assertTrue(is_placeholder_api_key("PUT_API_KEY_HERE"))
        self.assertFalse(is_placeholder_api_key("AIza-not-a-real-test-key"))

    def test_validate_config_rejects_inverted_thresholds(self) -> None:
        config = _valid_config()
        config["traffic"]["warning_delay_min"] = 30
        config["traffic"]["severe_delay_min"] = 20

        errors = validate_config(config)

        self.assertIn("traffic.warning_delay_min must be less than traffic.severe_delay_min", errors)


def _valid_config() -> dict[str, object]:
    return {
        "google": {"api_key": "PUT_API_KEY_HERE", "routes_api_url": "https://example.com"},
        "commute": {
            "origin_address": "Origin",
            "destination_address": "Destination",
            "timezone": "America/New_York",
        },
        "traffic": {
            "expected_shuttle_drive_min": 35,
            "estimated_transit_min_low": 45,
            "estimated_transit_min_high": 60,
            "warning_delay_min": 10,
            "severe_delay_min": 20,
            "transit_advantage_buffer_min": 10,
        },
        "imessage": {"send_enabled": False, "dry_run": True, "recipients": ["person@example.com"]},
        "message": {"template": "{recommendation}"},
        "schedule": {"enabled": True, "times": ["06:00"]},
        "storage": {"sqlite_path": "history.sqlite3", "retention_days": 7},
        "logging": {"log_path": "bot.log", "log_level": "INFO"},
    }


if __name__ == "__main__":
    unittest.main()
