from __future__ import annotations

import unittest

from decision import TAKE_NJ_TRANSIT, TAKE_SHUTTLE, TRAFFIC_ELEVATED, make_decision


class DecisionTests(unittest.TestCase):
    def test_normal_traffic_takes_shuttle(self) -> None:
        result = make_decision(
            current_drive_min=42,
            baseline_min=35,
            transit_min_low=45,
            transit_min_high=60,
            warning_delay_min=10,
            severe_delay_min=20,
            transit_advantage_buffer_min=10,
        )

        self.assertEqual(result.recommendation, TAKE_SHUTTLE)
        self.assertIn("셔틀", result.reason)

    def test_elevated_traffic_still_accepts_shuttle(self) -> None:
        result = make_decision(
            current_drive_min=48,
            baseline_min=35,
            transit_min_low=45,
            transit_min_high=60,
            warning_delay_min=10,
            severe_delay_min=20,
            transit_advantage_buffer_min=10,
        )

        self.assertEqual(result.recommendation, TRAFFIC_ELEVATED)
        self.assertIn("☕", result.reason)

    def test_severe_delay_takes_nj_transit(self) -> None:
        result = make_decision(
            current_drive_min=55,
            baseline_min=35,
            transit_min_low=45,
            transit_min_high=60,
            warning_delay_min=10,
            severe_delay_min=20,
            transit_advantage_buffer_min=10,
        )

        self.assertEqual(result.recommendation, TAKE_NJ_TRANSIT)
        self.assertIn("NJ Transit", result.reason)

    def test_transit_advantage_overrides_lower_delay(self) -> None:
        result = make_decision(
            current_drive_min=62,
            baseline_min=50,
            transit_min_low=35,
            transit_min_high=45,
            warning_delay_min=20,
            severe_delay_min=30,
            transit_advantage_buffer_min=10,
        )

        self.assertEqual(result.recommendation, TAKE_NJ_TRANSIT)
        self.assertIn("🚆", result.reason)


if __name__ == "__main__":
    unittest.main()
