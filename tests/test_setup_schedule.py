from __future__ import annotations

from pathlib import Path
import unittest

from setup_schedule import build_plist, build_wrapper_script


class SetupScheduleTests(unittest.TestCase):
    def test_build_plist_uses_local_wrapper_and_logs(self) -> None:
        plist = build_plist(
            {"schedule": {"enabled": True, "times": ["06:50"]}},
            Path("/repo/config.yaml"),
            wrapper_path=Path("/Users/me/Library/Application Support/CommuteBot/run_commutebot.sh"),
            stdout_path=Path("/Users/me/Library/Logs/CommuteBot/morning.stdout.log"),
            stderr_path=Path("/Users/me/Library/Logs/CommuteBot/morning.stderr.log"),
        )

        self.assertEqual(
            plist["ProgramArguments"],
            ["/bin/zsh", "/Users/me/Library/Application Support/CommuteBot/run_commutebot.sh"],
        )
        self.assertEqual(plist["WorkingDirectory"], "/private/tmp")
        self.assertEqual(plist["StandardOutPath"], "/Users/me/Library/Logs/CommuteBot/morning.stdout.log")
        self.assertEqual(plist["StandardErrorPath"], "/Users/me/Library/Logs/CommuteBot/morning.stderr.log")
        self.assertEqual(plist["StartCalendarInterval"], [{"Hour": 6, "Minute": 50}])

    def test_build_wrapper_quotes_paths_and_forwards_args(self) -> None:
        script = build_wrapper_script(
            Path("/repo dir/config.yaml"),
            python_path=Path("/python dir/python3"),
            project_dir=Path("/repo dir"),
        )

        self.assertIn("cd /private/tmp", script)
        self.assertIn("'/python dir/python3' -B '/repo dir/main.py' --config '/repo dir/config.yaml' \"$@\"", script)


if __name__ == "__main__":
    unittest.main()
