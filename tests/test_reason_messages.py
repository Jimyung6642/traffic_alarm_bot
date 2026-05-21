from __future__ import annotations

import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from decision import DecisionResult, TAKE_NJ_TRANSIT, TAKE_SHUTTLE
from google_weather import CurrentWeather, DailyWeather
from reason_messages import compose_reason


class ReasonMessagesTests(unittest.TestCase):
    def test_reason_includes_weather_context_when_weather_is_available(self) -> None:
        reason = compose_reason(
            decision=DecisionResult(
                recommendation=TAKE_SHUTTLE,
                reason="Traffic base reason.",
                delay_min=-5,
                transit_midpoint_min=50,
            ),
            now=datetime(2026, 5, 20, 6, 0, tzinfo=ZoneInfo("America/New_York")),
            current_weather=CurrentWeather(
                condition="Sunny",
                temperature_degrees=65,
                feels_like_degrees=65,
                temperature_unit="FAHRENHEIT",
                precipitation_percent=0,
            ),
            daily_weather=DailyWeather(
                condition="Partly sunny",
                high_degrees=72,
                low_degrees=58,
                temperature_unit="FAHRENHEIT",
                precipitation_percent=10,
                uv_index=4,
            ),
        )

        self.assertIn("Traffic base reason.", reason)
        self.assertIn("셔틀", reason)

    def test_wet_weather_and_transit_recommendation_mentions_umbrella_or_waterproofing(self) -> None:
        reason = compose_reason(
            decision=DecisionResult(
                recommendation=TAKE_NJ_TRANSIT,
                reason="Traffic base reason.",
                delay_min=30,
                transit_midpoint_min=50,
            ),
            now=datetime(2026, 5, 20, 6, 0, tzinfo=ZoneInfo("America/New_York")),
            current_weather=CurrentWeather(
                condition="Rain showers",
                temperature_degrees=55,
                feels_like_degrees=55,
                temperature_unit="FAHRENHEIT",
                precipitation_percent=70,
            ),
        )

        self.assertIn("Traffic base reason.", reason)
        self.assertTrue("우산" in reason or "방수" in reason)
        self.assertTrue("NJ Transit" in reason or "트랜짓" in reason or "셔틀 지연" in reason)

    def test_weather_unavailable_returns_base_traffic_reason(self) -> None:
        decision = DecisionResult(
            recommendation=TAKE_SHUTTLE,
            reason="Traffic base reason.",
            delay_min=-5,
            transit_midpoint_min=50,
        )

        reason = compose_reason(
            decision=decision,
            now=datetime(2026, 5, 20, 6, 0, tzinfo=ZoneInfo("America/New_York")),
        )

        self.assertEqual(reason, "Traffic base reason.")


if __name__ == "__main__":
    unittest.main()
