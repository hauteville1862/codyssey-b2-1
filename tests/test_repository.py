import tempfile
import unittest
from pathlib import Path
from typing import Iterator

from budget_app.errors import BudgetAppError
from budget_app.models import Transaction
from budget_app.repository import TransactionRepository


def make_transaction(tx_id: str = "TX-000001", memo: str = "") -> Transaction:
    return Transaction(tx_id, "expense", "2024-01-15", 15000, "food", memo, ["meal"])


VALID_LINE = (
    '{"id": "TX-000001", "type": "expense", "date": "2024-01-15", '
    '"amount": 15000, "category": "food"}\n'
)


class TransactionRepositoryTest(unittest.TestCase):
    def setUp(self) -> None:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        self.path = Path(temp_dir.name) / "transactions.jsonl"
        self.path.touch()
        self.repository = TransactionRepository(self.path)

    def test_appended_transaction_can_be_read_back(self) -> None:
        transaction = make_transaction()

        self.repository.append(transaction)

        self.assertEqual(list(self.repository.iter_all()), [transaction])

    def test_empty_file_has_no_transactions(self) -> None:
        self.assertEqual(list(self.repository.iter_all()), [])

    def test_iter_all_reads_lazily_one_line_at_a_time(self) -> None:
        self.path.write_text(VALID_LINE + "{broken\n", encoding="utf-8")

        transactions = self.repository.iter_all()

        self.assertEqual(next(transactions).id, "TX-000001")
        with self.assertRaises(BudgetAppError):
            next(transactions)

    def test_special_characters_in_memo_stay_on_one_line(self) -> None:
        memo = '점심, "김밥"\n둘째 줄'

        self.repository.append(make_transaction(memo=memo))

        self.assertEqual(next(self.repository.iter_all()).memo, memo)
        self.assertEqual(len(self.path.read_text(encoding="utf-8").splitlines()), 1)

    def test_broken_json_reports_file_and_line_number(self) -> None:
        self.path.write_text(VALID_LINE + "{broken\n", encoding="utf-8")

        with self.assertRaises(BudgetAppError) as caught:
            list(self.repository.iter_all())

        self.assertIn("transactions.jsonl", caught.exception.message)
        self.assertIn("2번째 줄", caught.exception.message)
        self.assertTrue(caught.exception.hint)

    def test_invalid_fields_report_file_and_line_number(self) -> None:
        self.path.write_text(
            VALID_LINE + '{"id": "TX-000002", "amount": true}\n', encoding="utf-8"
        )

        with self.assertRaises(BudgetAppError) as caught:
            list(self.repository.iter_all())

        self.assertIn("transactions.jsonl", caught.exception.message)
        self.assertIn("2번째 줄", caught.exception.message)

    def test_non_object_line_reports_line_number(self) -> None:
        self.path.write_text("[1, 2]\n", encoding="utf-8")

        with self.assertRaises(BudgetAppError) as caught:
            list(self.repository.iter_all())

        self.assertIn("1번째 줄", caught.exception.message)

    def test_replace_all_rewrites_file_without_temp_file(self) -> None:
        self.repository.append(make_transaction("TX-000001"))
        replacement = make_transaction("TX-000002")

        self.repository.replace_all([replacement])

        self.assertEqual(list(self.repository.iter_all()), [replacement])
        self.assertEqual([p.name for p in self.path.parent.iterdir()], [self.path.name])

    def test_failure_while_writing_keeps_original_and_removes_temp_file(self) -> None:
        original = make_transaction("TX-000001")
        self.repository.append(original)

        def failing_transactions() -> Iterator[Transaction]:
            yield make_transaction("TX-000002")
            raise OSError("disk full")

        with self.assertRaises(OSError):
            self.repository.replace_all(failing_transactions())

        self.assertEqual(list(self.repository.iter_all()), [original])
        self.assertEqual([p.name for p in self.path.parent.iterdir()], [self.path.name])

    def test_find_returns_matching_transaction_or_none(self) -> None:
        transaction = make_transaction("TX-000007")
        self.repository.append(transaction)

        self.assertEqual(self.repository.find("TX-000007"), transaction)
        self.assertIsNone(self.repository.find("TX-999999"))

    def test_next_id_starts_from_one(self) -> None:
        self.assertEqual(self.repository.next_id(), "TX-000001")

    def test_next_id_uses_largest_number_not_last_line(self) -> None:
        self.repository.append(make_transaction("TX-000012"))
        self.repository.append(make_transaction("TX-000005"))

        self.assertEqual(self.repository.next_id(), "TX-000013")

    def test_next_ids_returns_consecutive_numbers(self) -> None:
        self.repository.append(make_transaction("TX-000012"))

        self.assertEqual(self.repository.next_ids(2), ["TX-000013", "TX-000014"])

    def test_next_id_compares_numbers_beyond_six_digits(self) -> None:
        self.repository.append(make_transaction("TX-999999"))
        self.repository.append(make_transaction("TX-1000000"))

        self.assertEqual(self.repository.next_id(), "TX-1000001")


if __name__ == "__main__":
    unittest.main()
