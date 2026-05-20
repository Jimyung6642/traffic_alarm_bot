from __future__ import annotations

import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from decision import DecisionResult, TAKE_SHUTTLE
from google_routes import RouteDuration
from main import _message_context


class MainMessageTests(unittest.TestCase):
    def test_message_context_includes_current_transit_min(self) -> None:
        config = {
            "commute": {
                "origin_address": "Origin",
                "destination_address": "Destination",
                "transit_origin_address": "Transit Origin",
                "transit_destination_address": "Transit Destination",
            },
            "traffic": {
                "expected_shuttle_drive_min": 25,
                "estimated_transit_min_low": 45,
                "estimated_transit_min_high": 60,
            },
        }

        context = _message_context(
            config,
            now=datetime(2026, 5, 20, 6, 0, tzinfo=ZoneInfo("America/New_York")),
            route=RouteDuration(duration_min=15.4, static_duration_min=None, distance_meters=None),
            transit_route=RouteDuration(duration_min=12.6, static_duration_min=None, distance_meters=None),
            decision=DecisionResult(
                recommendation=TAKE_SHUTTLE,
                reason="Traffic is close to your normal shuttle baseline.",
                delay_min=-9.6,
                transit_midpoint_min=52.5,
            ),
        )

        self.assertEqual(context["current_transit_min"], "13")
        self.assertEqual(context["transit_origin_address"], "Transit Origin")
        self.assertEqual(context["transit_destination_address"], "Transit Destination")


if __name__ == "__main__":
    unittest.main()
