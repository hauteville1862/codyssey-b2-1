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


class CategoryRemoveCommandTest(AppTestCase):
    def test_unused_category_is_removed_interactively(self) -> None:
        result = self.run_in_data_dir("category", "remove", stdin="rent\n")

        self.assertEqual(result.returncode, 0)
        self.assertIn("[삭제 완료] category=rent", result.stdout)
        self.assertNotIn("- rent", self.run_in_data_dir("category", "list").stdout)

    def test_category_in_use_exits_with_error_and_hint(self) -> None:
        self.run_in_data_dir("add", stdin="2024-01-01\nexpense\nfood\n1000\n\n\n")

        result = self.run_in_data_dir("category", "remove", stdin="food\n")

        self.assertEqual(result.returncode, 1)
        self.assertIn("[오류]", result.stderr)
        self.assertIn("[힌트]", result.stderr)
        self.assertIn("- food", self.run_in_data_dir("category", "list").stdout)


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


class SearchCommandTest(AppTestCase):
    def setUp(self) -> None:
        super().setUp()
        for day in range(1, 22):
            memo = "점심" if day == 21 else "간식"
            self.run_in_data_dir(
                "add", stdin=f"2024-01-{day:02d}\nexpense\nfood\n1000\n{memo}\nmeal\n"
            )

    def test_options_filter_and_print_newest_first(self) -> None:
        result = self.run_in_data_dir(
            "search",
            "--from", "2024-01-20",
            "--to", "2024-01-21",
            "--category", "food",
            "--type", "expense",
            "--tag", "meal",
        )  # fmt: skip

        self.assertEqual(result.returncode, 0)
        lines = result.stdout.splitlines()
        self.assertEqual(len(lines), 2)
        self.assertIn("2024-01-21", lines[0])
        self.assertIn("2024-01-20", lines[1])

    def test_q_option_searches_memo(self) -> None:
        result = self.run_in_data_dir("search", "--q", "점심")

        self.assertEqual(len(result.stdout.splitlines()), 1)

    def test_full_result_page_prints_limit_notice(self) -> None:
        result = self.run_in_data_dir("search")

        self.assertEqual(len(result.stdout.splitlines()), 21)
        self.assertIn("최대 20건 표시. 더 보려면 --limit", result.stdout)

    def test_limit_option_changes_count_and_notice(self) -> None:
        result = self.run_in_data_dir("search", "--limit", "2")

        self.assertEqual(len(result.stdout.splitlines()), 3)
        self.assertIn("최대 2건 표시", result.stdout)

    def test_result_smaller_than_limit_has_no_notice(self) -> None:
        result = self.run_in_data_dir("search", "--q", "점심")

        self.assertNotIn("최대", result.stdout)

    def test_no_match_prints_notice(self) -> None:
        result = self.run_in_data_dir("search", "--category", "rent")

        self.assertEqual(result.returncode, 0)
        self.assertIn("조건에 맞는 거래가 없습니다", result.stdout)

    def test_invalid_values_exit_with_error_and_hint(self) -> None:
        wrong = [
            ["--from", "abc"],
            ["--to", "2024-02-30"],
            ["--type", "gift"],
            ["--from", "2024-02-01", "--to", "2024-01-01"],
        ]
        for options in wrong:
            with self.subTest(options=options):
                result = self.run_in_data_dir("search", *options)

                self.assertEqual(result.returncode, 1)
                self.assertIn("[오류]", result.stderr)
                self.assertIn("[힌트]", result.stderr)


class DeleteCommandTest(AppTestCase):
    def test_delete_prints_success_and_removes_transaction(self) -> None:
        self.run_in_data_dir("add", stdin="2024-01-01\nexpense\nfood\n1000\n\n\n")

        result = self.run_in_data_dir("delete", "--id", "TX-000001")

        self.assertEqual(result.returncode, 0)
        self.assertIn("[삭제 완료] id=TX-000001", result.stdout)
        self.assertIn("거래 내역이 없습니다", self.run_in_data_dir("list").stdout)

    def test_unknown_id_prints_error_and_hint(self) -> None:
        result = self.run_in_data_dir("delete", "--id", "TX-999999")

        self.assertEqual(result.returncode, 1)
        self.assertIn("없는 데이터", result.stderr)
        self.assertIn("[힌트]", result.stderr)


class UpdateCommandTest(AppTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.run_in_data_dir("add", stdin="2024-01-01\nexpense\nfood\n1000\n점심\nmeal\n")

    def test_update_prints_success_and_changes_only_given_option(self) -> None:
        result = self.run_in_data_dir("update", "--id", "TX-000001", "--amount", "20000")

        self.assertEqual(result.returncode, 0)
        self.assertIn("[수정 완료] id=TX-000001", result.stdout)
        listed = self.run_in_data_dir("list").stdout
        self.assertIn("TX-000001 | 2024-01-01 | expense | food | 20000 | 점심", listed)

    def test_empty_memo_option_clears_memo(self) -> None:
        self.run_in_data_dir("update", "--id", "TX-000001", "--memo", "")

        self.assertNotIn("점심", self.run_in_data_dir("list").stdout)

    def test_no_change_option_exits_with_error(self) -> None:
        result = self.run_in_data_dir("update", "--id", "TX-000001")

        self.assertEqual(result.returncode, 1)
        self.assertIn("[힌트]", result.stderr)

    def test_unknown_id_exits_with_error(self) -> None:
        result = self.run_in_data_dir("update", "--id", "TX-999999", "--amount", "5")

        self.assertEqual(result.returncode, 1)
        self.assertIn("없는 데이터", result.stderr)


class SummaryCommandTest(AppTestCase):
    def setUp(self) -> None:
        super().setUp()
        for record in [
            "2024-01-05\nincome\nsalary\n3000000\n\n\n",
            "2024-01-10\nexpense\nrent\n150000\n\n\n",
            "2024-01-11\nexpense\nfood\n45000\n\n\n",
        ]:
            self.run_in_data_dir("add", stdin=record)

    def test_summary_prints_totals_and_top_categories(self) -> None:
        result = self.run_in_data_dir("summary", "--month", "2024-01", "--top", "1")

        self.assertEqual(result.returncode, 0)
        self.assertIn("총 수입: 3000000원", result.stdout)
        self.assertIn("총 지출: 195000원", result.stdout)
        self.assertIn("잔액: 2805000원", result.stdout)
        self.assertIn("지출 TOP 1", result.stdout)
        self.assertIn("1) rent 150000원", result.stdout)
        self.assertNotIn("food", result.stdout)

    def test_month_without_data_prints_no_data(self) -> None:
        result = self.run_in_data_dir("summary", "--month", "2023-12")

        self.assertEqual(result.returncode, 0)
        self.assertIn("데이터 없음", result.stdout)

    def test_invalid_month_exits_with_error_and_hint(self) -> None:
        result = self.run_in_data_dir("summary", "--month", "2024-13")

        self.assertEqual(result.returncode, 1)
        self.assertIn("[힌트]", result.stderr)

    def test_missing_month_is_usage_error(self) -> None:
        self.assertEqual(self.run_in_data_dir("summary").returncode, 2)


class BudgetCommandTest(AppTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.run_in_data_dir("add", stdin="2024-01-05\nexpense\nfood\n1000\n\n\n")

    def set_budget(self, amount: str) -> subprocess.CompletedProcess[str]:
        return self.run_in_data_dir(
            "budget", "set", "--month", "2024-01", "--amount", amount
        )

    def summary(self) -> str:
        return self.run_in_data_dir("summary", "--month", "2024-01").stdout

    def test_budget_set_prints_success(self) -> None:
        result = self.set_budget("5000")

        self.assertEqual(result.returncode, 0)
        self.assertIn("[저장 완료] 2024-01 예산 5000원", result.stdout)

    def test_summary_prints_usage_without_warning_inside_budget(self) -> None:
        self.set_budget("5000")

        output = self.summary()

        self.assertIn("예산: 5000원 (사용률 20.0%)", output)
        self.assertNotIn("[경고]", output)

    def test_exactly_full_budget_has_no_warning(self) -> None:
        self.set_budget("1000")

        output = self.summary()

        self.assertIn("사용률 100.0%", output)
        self.assertNotIn("[경고]", output)

    def test_over_budget_prints_warning(self) -> None:
        self.set_budget("999")

        self.assertIn("[경고] 예산을 1원 초과했습니다.", self.summary())

    def test_no_budget_prints_no_budget_line(self) -> None:
        self.assertNotIn("예산", self.summary())

    def test_budget_is_shown_for_month_without_transactions(self) -> None:
        self.run_in_data_dir("budget", "set", "--month", "2024-02", "--amount", "100")

        output = self.run_in_data_dir("summary", "--month", "2024-02").stdout

        self.assertIn("데이터 없음", output)
        self.assertIn("예산: 100원 (사용률 0.0%)", output)

    def test_invalid_amount_exits_with_error_and_hint(self) -> None:
        result = self.set_budget("0")

        self.assertEqual(result.returncode, 1)
        self.assertIn("[힌트]", result.stderr)


class ExportCommandTest(AppTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.out = self.data_dir.parent / "export.csv"
        self.run_in_data_dir("add", stdin="2024-01-15\nexpense\nfood\n1000\n\n\n")

    def test_export_prints_path_and_record_count(self) -> None:
        result = self.run_in_data_dir("export", "--out", str(self.out), "--month", "2024-01")

        self.assertEqual(result.returncode, 0)
        self.assertIn("(1 records)", result.stdout)
        self.assertTrue(self.out.exists())

    def test_invalid_conditions_exit_with_error_and_create_no_file(self) -> None:
        wrong = [
            [],
            ["--from", "2024-01-01"],
            ["--month", "2024-13"],
            ["--from", "abc", "--to", "2024-01-31"],
        ]
        for options in wrong:
            with self.subTest(options=options):
                result = self.run_in_data_dir("export", "--out", str(self.out), *options)

                self.assertEqual(result.returncode, 1)
                self.assertIn("[힌트]", result.stderr)
                self.assertFalse(self.out.exists())

    def test_existing_output_file_exits_with_error(self) -> None:
        self.run_in_data_dir("export", "--out", str(self.out), "--month", "2024-01")
        before = self.out.read_bytes()

        result = self.run_in_data_dir("export", "--out", str(self.out), "--month", "2023-01")

        self.assertEqual(result.returncode, 1)
        self.assertIn("[힌트]", result.stderr)
        self.assertEqual(self.out.read_bytes(), before)


class ImportCommandTest(AppTestCase):
    def test_sample_ok_file_is_imported_with_count(self) -> None:
        result = self.run_in_data_dir("import", "--from", "samples/import_ok.csv")

        self.assertEqual(result.returncode, 0)
        self.assertRegex(result.stdout, r"\[완료\] imported=[1-9]\d*, skipped=0")

    def test_sample_broken_file_changes_nothing_and_reports_rows(self) -> None:
        result = self.run_in_data_dir("import", "--from", "samples/import_broken.csv")

        self.assertEqual(result.returncode, 1)
        self.assertRegex(result.stderr, r"\d+번째 줄")
        self.assertIn("[힌트]", result.stderr)
        self.assertIn("거래 내역이 없습니다", self.run_in_data_dir("list").stdout)

    def test_missing_file_prints_hint_without_traceback(self) -> None:
        result = self.run_in_data_dir("import", "--from", "samples/no_such_file.csv")

        self.assertEqual(result.returncode, 1)
        self.assertIn("[힌트]", result.stderr)
        self.assertNotIn("Traceback", result.stderr)


class ExecutionLogTest(AppTestCase):
    def log_lines(self) -> list[str]:
        path = self.data_dir / "app.log"
        return path.read_text(encoding="utf-8").splitlines()

    def test_success_is_recorded_with_time_and_command(self) -> None:
        self.run_in_data_dir("category", "list")

        self.assertRegex(
            self.log_lines()[0],
            r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} category list 성공$",
        )

    def test_failure_is_recorded_and_error_still_reaches_user(self) -> None:
        result = self.run_in_data_dir("delete", "--id", "TX-999999")

        self.assertEqual(result.returncode, 1)
        self.assertIn("없는 데이터", result.stderr)
        self.assertRegex(self.log_lines()[0], r" delete 실패$")

    def test_interrupted_input_is_recorded_as_failure(self) -> None:
        result = self.run_in_data_dir("add", stdin="2024-01-15\n")

        self.assertEqual(result.returncode, 1)
        self.assertNotIn("Traceback", result.stderr)
        self.assertRegex(self.log_lines()[0], r" add 실패$")

    def test_each_run_adds_one_line(self) -> None:
        self.run_in_data_dir("category", "list")
        self.run_in_data_dir("list")

        self.assertEqual(len(self.log_lines()), 2)

    def test_log_does_not_contain_amount_or_memo(self) -> None:
        self.run_in_data_dir(
            "add", stdin="2024-01-15\nexpense\nfood\n987654\n비밀메모\nmeal\n"
        )

        log_text = "\n".join(self.log_lines())
        self.assertRegex(log_text, r" add 성공$")
        self.assertNotIn("987654", log_text)
        self.assertNotIn("비밀메모", log_text)

    def test_command_succeeds_when_log_cannot_be_written(self) -> None:
        (self.data_dir / "app.log").mkdir(parents=True)

        result = self.run_in_data_dir("category", "list")

        self.assertEqual(result.returncode, 0)
        self.assertIn("- food", result.stdout)
        self.assertEqual(result.stderr, "")


class AllCommandsHelpTest(unittest.TestCase):
    def test_every_command_prints_help_with_exit_zero(self) -> None:
        commands = [
            ["add"],
            ["list"],
            ["search"],
            ["summary"],
            ["budget"],
            ["budget", "set"],
            ["category"],
            ["category", "add"],
            ["category", "list"],
            ["category", "remove"],
            ["update"],
            ["delete"],
            ["import"],
            ["export"],
        ]
        for command in commands:
            with self.subTest(command=command):
                result = run_app(*command, "--help")

                self.assertEqual(result.returncode, 0)
                self.assertIn("usage", result.stdout.lower())


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

    def test_interrupted_input_prints_error_on_next_line(self) -> None:
        failures: list[BaseException] = [KeyboardInterrupt(), EOFError()]
        for failure in failures:
            with self.subTest(failure=type(failure).__name__):
                code, stderr = self.run_failing(failure)

                self.assertEqual(code, 1)
                self.assertEqual(
                    stderr,
                    "\n[오류] 입력이 중단되었습니다.\n[힌트] 명령을 다시 실행하세요.\n",
                )


class LineEditingTest(unittest.TestCase):
    """한글 지우기와 화살표 키는 readline이 처리한다. 여기서는 불러오는지만 확인한다."""

    @unittest.skipIf(sys.platform == "win32", "윈도우에는 readline이 없다.")
    def test_cli_loads_readline_for_line_editing(self) -> None:
        code = "import sys, budget_app.cli; print('readline' in sys.modules)"
        result = subprocess.run(
            [sys.executable, "-c", code],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.stdout.strip(), "True")


if __name__ == "__main__":
    unittest.main()
