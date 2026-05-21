from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from google_weather import (
    CURRENT_CONDITIONS_URL,
    DAILY_FORECAST_URL,
    fetch_current_weather,
    fetch_daily_weather,
)


class GoogleWeatherTests(unittest.TestCase):
    @patch("google_weather.requests.get")
    def test_current_weather_uses_configured_location(self, mock_get: Mock) -> None:
        mock_get.return_value = _mock_response(
            {
                "weatherCondition": {"description": {"text": "Sunny"}},
                "temperature": {"degrees": 56.6, "unit": "FAHRENHEIT"},
                "feelsLikeTemperature": {"degrees": 55.7, "unit": "FAHRENHEIT"},
                "precipitation": {"probability": {"percent": 5}},
            }
        )

        weather = fetch_current_weather(_valid_config())

        self.assertEqual(weather.condition, "Sunny")
        self.assertAlmostEqual(weather.temperature_degrees or 0, 56.6)
        self.assertEqual(mock_get.call_args.args[0], CURRENT_CONDITIONS_URL)
        params = mock_get.call_args.kwargs["params"]
        self.assertEqual(params["location.latitude"], 40.85603)
        self.assertEqual(params["location.longitude"], -73.97477)
        self.assertEqual(params["unitsSystem"], "IMPERIAL")

    @patch("google_weather.requests.get")
    def test_daily_weather_uses_days_parameter(self, mock_get: Mock) -> None:
        mock_get.return_value = _mock_response(
            {
                "forecastDays": [
                    {
                        "daytimeForecast": {
                            "weatherCondition": {"description": {"text": "Partly sunny"}},
                            "precipitation": {"probability": {"percent": 15}},
                            "uvIndex": 4,
                        },
                        "maxTemperature": {"degrees": 74.4, "unit": "FAHRENHEIT"},
                        "minTemperature": {"degrees": 61.2, "unit": "FAHRENHEIT"},
                    }
                ]
            }
        )

        weather = fetch_daily_weather(_valid_config())

        self.assertEqual(weather.condition, "Partly sunny")
        self.assertAlmostEqual(weather.high_degrees or 0, 74.4)
        self.assertAlmostEqual(weather.low_degrees or 0, 61.2)
        self.assertEqual(weather.precipitation_percent, 15)
        self.assertEqual(weather.uv_index, 4)
        self.assertEqual(mock_get.call_args.args[0], DAILY_FORECAST_URL)
        self.assertEqual(mock_get.call_args.kwargs["params"]["days"], 1)


def _mock_response(body: dict[str, object]) -> Mock:
    response = Mock()
    response.status_code = 200
    response.json.return_value = body
    return response


def _valid_config() -> dict[str, object]:
    return {
        "google": {"api_key": "AIza-not-real"},
        "weather": {
            "enabled": True,
            "latitude": 40.85603,
            "longitude": -73.97477,
            "location_label": "Constitution Park, Fort Lee",
            "units_system": "IMPERIAL",
            "daily_days": 1,
        },
    }


if __name__ == "__main__":
    unittest.main()
