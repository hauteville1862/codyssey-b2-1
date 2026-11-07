import subprocess
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def run_app(*args: str) -> subprocess.CompletedProcess[str]:
    """실제 명령처럼 python -m budget_app을 실행하고 결과를 돌려준다."""
    return subprocess.run(
        [sys.executable, "-m", "budget_app", *args],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


class HelpTest(unittest.TestCase):
    def test_help_shows_usage_and_data_dir_option(self) -> None:
        result = run_app("--help")

        self.assertEqual(result.returncode, 0)
        self.assertIn("usage", result.stdout.lower())
        self.assertIn("--data-dir", result.stdout)


class InvalidUsageTest(unittest.TestCase):
    def assert_usage_error(self, result: subprocess.CompletedProcess[str]) -> None:
        self.assertEqual(result.returncode, 2)
        self.assertIn("[오류]", result.stderr)
        self.assertIn("[힌트]", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_unknown_option_prints_error_and_hint(self) -> None:
        self.assert_usage_error(run_app("--unknown-option"))

    def test_missing_command_prints_error_and_hint(self) -> None:
        self.assert_usage_error(run_app())


if __name__ == "__main__":
    unittest.main()
