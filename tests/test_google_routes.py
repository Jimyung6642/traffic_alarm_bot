from __future__ import annotations

import unittest

from google_routes import parse_duration_to_minutes


class GoogleRoutesTests(unittest.TestCase):
    def test_parse_duration_to_minutes(self) -> None:
        self.assertAlmostEqual(parse_duration_to_minutes("3520s"), 58.6666667)

    def test_parse_duration_rejects_bad_value(self) -> None:
        with self.assertRaises(ValueError):
            parse_duration_to_minutes("58m")


if __name__ == "__main__":
    unittest.main()
