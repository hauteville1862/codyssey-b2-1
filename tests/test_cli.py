import argparse
import contextlib
import io
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Callable

from budget_app.decorators import handle_errors
from budget_app.errors import BudgetAppError

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def run_app(*args: str, stdin: str = "") -> subprocess.CompletedProcess[str]:
    """실제 명령처럼 python -m budget_app을 실행하고 결과를 돌려준다."""
    return subprocess.run(
        [sys.executable, "-m", "budget_app", *args],
        cwd=PROJECT_ROOT,
        input=stdin,
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


class AppTestCase(unittest.TestCase):
    def setUp(self) -> None:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        self.data_dir = Path(temp_dir.name) / "data"

    def run_in_data_dir(
        self, *args: str, stdin: str = ""
    ) -> subprocess.CompletedProcess[str]:
        return run_app("--data-dir", str(self.data_dir), *args, stdin=stdin)


class CategoryCommandTest(AppTestCase):
    def test_first_run_creates_three_files_and_lists_defaults(self) -> None:
        result = self.run_in_data_dir("category", "list")

        self.assertEqual(result.returncode, 0)
        for name in ["food", "transport", "rent", "etc", "salary"]:
            self.assertIn(f"- {name}", result.stdout)
        for name in ["transactions.jsonl", "categories.jsonl", "budgets.jsonl"]:
            self.assertTrue((self.data_dir / name).exists(), name)

    def test_added_category_survives_next_run(self) -> None:
        added = self.run_in_data_dir("category", "add", stdin="pet\n")
        listed = self.run_in_data_dir("category", "list")

        self.assertEqual(added.returncode, 0)
        self.assertIn("[저장 완료] category=pet", added.stdout)
        self.assertIn("- pet", listed.stdout)

    def test_duplicate_category_exits_with_error(self) -> None:
        result = self.run_in_data_dir("category", "add", stdin="food\n")

        self.assertEqual(result.returncode, 1)
        self.assertIn("[오류]", result.stderr)
        self.assertIn("[힌트]", result.stderr)

    def test_unknown_option_on_real_command_exits_with_usage_error(self) -> None:
        result = self.run_in_data_dir("category", "list", "--unknown-option")

        self.assertEqual(result.returncode, 2)
        self.assertIn("--unknown-option", result.stderr)
        self.assertIn("[힌트]", result.stderr)

    def test_data_dir_that_is_a_file_prints_hint_without_traceback(self) -> None:
        self.data_dir.parent.mkdir(exist_ok=True)
        self.data_dir.write_text("not a folder", encoding="utf-8")

        result = self.run_in_data_dir("category", "list")

        self.assertEqual(result.returncode, 1)
        self.assertIn("[힌트]", result.stderr)
        self.assertNotIn("Traceback", result.stderr)


class AddCommandTest(AppTestCase):
    def transaction_lines(self) -> list[str]:
        path = self.data_dir / "transactions.jsonl"
        return path.read_text(encoding="utf-8").splitlines()

    def test_add_saves_transaction_and_prints_id(self) -> None:
        result = self.run_in_data_dir(
            "add", stdin="2024-01-15\nexpense\nfood\n15000\n점심\nmeal, lunch\n"
        )

        self.assertEqual(result.returncode, 0)
        self.assertIn("[저장 완료] id=TX-000001", result.stdout)
        self.assertEqual(len(self.transaction_lines()), 1)
        self.assertIn('"tags": ["meal", "lunch"]', self.transaction_lines()[0])

    def test_invalid_answers_are_asked_again(self) -> None:
        result = self.run_in_data_dir(
            "add",
            stdin="2024-13-40\n2024-01-15\ngift\nexpense\nnope\nfood\n0\n15000\n\n\n",
        )

        self.assertEqual(result.returncode, 0)
        self.assertIn("[저장 완료] id=TX-000001", result.stdout)
        self.assertEqual(result.stderr.count("[오류]"), 4)
        self.assertEqual(result.stderr.count("[힌트]"), 4)
        self.assertIn("food", result.stderr)

    def test_input_ending_midway_saves_nothing(self) -> None:
        result = self.run_in_data_dir("add", stdin="2024-01-15\nexpense\n")

        self.assertEqual(result.returncode, 1)
        self.assertIn("[오류]", result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertEqual(self.transaction_lines(), [])


class ListCommandTest(AppTestCase):
    def add(self, date: str, memo: str = "") -> None:
        result = self.run_in_data_dir(
            "add", stdin=f"{date}\nexpense\nfood\n1000\n{memo}\n\n"
        )
        self.assertEqual(result.returncode, 0)

    def test_list_prints_newest_first_after_restart(self) -> None:
        self.add("2024-01-01", "오래된 거래")
        self.add("2024-03-01", "최신 거래")

        result = self.run_in_data_dir("list")

        self.assertEqual(result.returncode, 0)
        lines = result.stdout.splitlines()
        self.assertIn("TX-000002 | 2024-03-01 | expense | food | 1000 | 최신", lines[0])
        self.assertIn("TX-000001 | 2024-01-01", lines[1])

    def test_limit_option_restricts_output(self) -> None:
        self.add("2024-01-01")
        self.add("2024-03-01")

        result = self.run_in_data_dir("list", "--limit", "1")

        self.assertEqual(len(result.stdout.splitlines()), 1)
        self.assertIn("2024-03-01", result.stdout)

    def test_limit_below_one_is_usage_error(self) -> None:
        for value in ["0", "-1", "abc"]:
            with self.subTest(value=value):
                result = self.run_in_data_dir("list", f"--limit={value}")

                self.assertEqual(result.returncode, 2)
                self.assertIn("[힌트]", result.stderr)

    def test_empty_data_prints_notice(self) -> None:
        result = self.run_in_data_dir("list")

        self.assertEqual(result.returncode, 0)
        self.assertIn("거래 내역이 없습니다", result.stdout)


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
