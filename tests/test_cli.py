import argparse
import contextlib
import io
import subprocess
import sys
import unittest
from pathlib import Path
from typing import Callable

from budget_app.decorators import handle_errors
from budget_app.errors import BudgetAppError

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


class HandleErrorsTest(unittest.TestCase):
    def run_failing(self, error: BaseException) -> tuple[int, str]:
        def command(args: argparse.Namespace) -> int:
            raise error

        return self.run_command(command)

    def run_command(
        self, command: Callable[[argparse.Namespace], int]
    ) -> tuple[int, str]:
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            code = handle_errors(command)(argparse.Namespace())
        return code, stderr.getvalue()

    def test_returns_command_result_when_nothing_fails(self) -> None:
        code, stderr = self.run_command(lambda args: 0)

        self.assertEqual(code, 0)
        self.assertEqual(stderr, "")

    def test_budget_app_error_prints_its_message_and_hint(self) -> None:
        code, stderr = self.run_failing(BudgetAppError("원인 문구", "힌트 문구"))

        self.assertEqual(code, 1)
        self.assertIn("[오류] 원인 문구", stderr)
        self.assertIn("[힌트] 힌트 문구", stderr)

    def test_other_failures_print_error_and_hint_without_traceback(self) -> None:
        failures: list[BaseException] = [
            OSError("disk"),
            KeyboardInterrupt(),
            EOFError(),
            ValueError("bug"),
        ]
        for failure in failures:
            with self.subTest(failure=type(failure).__name__):
                code, stderr = self.run_failing(failure)

                self.assertEqual(code, 1)
                self.assertIn("[오류]", stderr)
                self.assertIn("[힌트]", stderr)
                self.assertNotIn("Traceback", stderr)


if __name__ == "__main__":
    unittest.main()
