from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from google_routes import fetch_traffic_duration, fetch_transit_duration, parse_duration_to_minutes


class GoogleRoutesTests(unittest.TestCase):
    def test_parse_duration_to_minutes(self) -> None:
        self.assertAlmostEqual(parse_duration_to_minutes("3520s"), 58.6666667)

    def test_parse_duration_rejects_bad_value(self) -> None:
        with self.assertRaises(ValueError):
            parse_duration_to_minutes("58m")

    @patch("google_routes.requests.post")
    def test_drive_route_uses_traffic_aware_routing(self, mock_post: Mock) -> None:
        mock_post.return_value = _mock_response({"routes": [{"duration": "1200s"}]})

        fetch_traffic_duration(_valid_config())

        payload = mock_post.call_args.kwargs["json"]
        self.assertEqual(payload["origin"]["address"], "Origin")
        self.assertEqual(payload["destination"]["address"], "Destination")
        self.assertEqual(payload["travelMode"], "DRIVE")
        self.assertEqual(payload["routingPreference"], "TRAFFIC_AWARE")

    @patch("google_routes.requests.post")
    def test_transit_route_uses_transit_mode_without_drive_routing_preference(self, mock_post: Mock) -> None:
        mock_post.return_value = _mock_response({"routes": [{"duration": "900s"}]})

        fetch_transit_duration(_valid_config())

        payload = mock_post.call_args.kwargs["json"]
        self.assertEqual(payload["origin"]["address"], "Transit Origin")
        self.assertEqual(payload["destination"]["address"], "Transit Destination")
        self.assertEqual(payload["travelMode"], "TRANSIT")
        self.assertNotIn("routingPreference", payload)


def _mock_response(body: dict[str, object]) -> Mock:
    response = Mock()
    response.status_code = 200
    response.json.return_value = body
    return response


def _valid_config() -> dict[str, object]:
    return {
        "google": {"api_key": "AIza-not-real", "routes_api_url": "https://example.com/routes"},
        "commute": {
            "origin_address": "Origin",
            "destination_address": "Destination",
            "transit_origin_address": "Transit Origin",
            "transit_destination_address": "Transit Destination",
        },
    }


if __name__ == "__main__":
    unittest.main()
