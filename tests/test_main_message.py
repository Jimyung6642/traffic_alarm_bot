from __future__ import annotations

import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from decision import DecisionResult, TAKE_SHUTTLE
from google_routes import RouteDuration
from google_weather import CurrentWeather, DailyWeather
from main import _message_context, _render_configured_message


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
            "weather": {"location_label": "Constitution Park, Fort Lee"},
        }

        context = _message_context(
            config,
            now=datetime(2026, 5, 20, 6, 0, tzinfo=ZoneInfo("America/New_York")),
            route=RouteDuration(duration_min=15.4, static_duration_min=None, distance_meters=None),
            transit_route=RouteDuration(duration_min=12.6, static_duration_min=None, distance_meters=None),
            current_weather=CurrentWeather(
                condition="Sunny",
                temperature_degrees=56.6,
                feels_like_degrees=55.7,
                temperature_unit="FAHRENHEIT",
                precipitation_percent=5,
            ),
            daily_weather=DailyWeather(
                condition="Partly sunny",
                high_degrees=74.4,
                low_degrees=61.2,
                temperature_unit="FAHRENHEIT",
                precipitation_percent=15,
                uv_index=4,
            ),
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
        self.assertEqual(context["weather_location"], "Constitution Park, Fort Lee")
        self.assertEqual(context["current_temp_f"], "57")
        self.assertEqual(context["current_feels_like_f"], "56")
        self.assertEqual(context["current_precip_percent"], "5")
        self.assertEqual(context["daily_high_f"], "74")
        self.assertEqual(context["daily_low_f"], "61")
        self.assertEqual(context["daily_precip_percent"], "15")
        self.assertEqual(context["daily_uv_index"], "4")
        self.assertIn("Sunny", context["current_weather_summary"])
        self.assertIn("Partly sunny", context["daily_weather_summary"])
        self.assertIn("Traffic is close to your normal shuttle baseline.", context["reason"])
        self.assertIn("셔틀", context["reason"])
        self.assertEqual(context["traffic_reason"], "Traffic is close to your normal shuttle baseline.")

    def test_rendered_message_keeps_traffic_recommendation_when_weather_is_unavailable(self) -> None:
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
            "message": {"template": "{recommendation}\n{current_weather_summary}\n{daily_weather_summary}"},
        }

        message = _render_configured_message(
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
            weather_error="Google Weather API quota was exceeded.",
        )

        self.assertIn(TAKE_SHUTTLE, message)
        self.assertIn("Unavailable", message)


if __name__ == "__main__":
    unittest.main()
