import unittest
from typing import Any, Callable

from budget_app.errors import BudgetAppError
from budget_app.models import (
    Transaction,
    parse_amount,
    parse_date,
    parse_month,
    parse_tags,
    parse_type,
)

VALID_RECORD: dict[str, Any] = {
    "id": "TX-000012",
    "type": "expense",
    "date": "2024-01-15",
    "amount": 15000,
    "category": "food",
    "memo": '점심, "김밥"',
    "tags": ["meal", "lunch"],
}


class ParseFunctionTest(unittest.TestCase):
    def assert_rejected(self, parse: Callable[[str], Any], value: str) -> None:
        with self.subTest(parse=parse.__name__, value=value):
            with self.assertRaises(BudgetAppError) as caught:
                parse(value)
            self.assertTrue(caught.exception.message)
            self.assertTrue(caught.exception.hint)

    def test_parse_date_accepts_exact_format(self) -> None:
        self.assertEqual(parse_date("2024-01-05"), "2024-01-05")

    def test_parse_date_rejects_invalid_values(self) -> None:
        for value in ["2024-1-5", "2024-02-30", "2024-13-40", "20240105", "abc", ""]:
            self.assert_rejected(parse_date, value)

    def test_parse_month_accepts_exact_format(self) -> None:
        self.assertEqual(parse_month("2024-01"), "2024-01")

    def test_parse_month_rejects_invalid_values(self) -> None:
        for value in ["2024-13", "2024-1", "2024-01-15", "abc", ""]:
            self.assert_rejected(parse_month, value)

    def test_parse_type_accepts_income_and_expense(self) -> None:
        self.assertEqual(parse_type("income"), "income")
        self.assertEqual(parse_type("expense"), "expense")

    def test_parse_type_rejects_other_values(self) -> None:
        for value in ["gift", "INCOME", ""]:
            self.assert_rejected(parse_type, value)

    def test_parse_amount_returns_positive_integer(self) -> None:
        self.assertEqual(parse_amount("15000"), 15000)

    def test_parse_amount_rejects_invalid_values(self) -> None:
        for value in ["0", "-1", "1.5", "1,000", "1_000", " 5", "abc", ""]:
            self.assert_rejected(parse_amount, value)

    def test_parse_tags_trims_spaces_and_drops_empty_items(self) -> None:
        self.assertEqual(parse_tags("a, b,,"), ["a", "b"])
        self.assertEqual(parse_tags(""), [])


class TransactionTest(unittest.TestCase):
    def test_from_dict_and_to_dict_keep_all_fields(self) -> None:
        transaction = Transaction.from_dict(VALID_RECORD)

        self.assertEqual(transaction.id, "TX-000012")
        self.assertEqual(transaction.amount, 15000)
        self.assertEqual(transaction.tags, ["meal", "lunch"])
        self.assertEqual(transaction.to_dict(), VALID_RECORD)

    def test_from_dict_uses_empty_memo_and_tags_when_missing(self) -> None:
        record = {k: v for k, v in VALID_RECORD.items() if k not in ("memo", "tags")}

        transaction = Transaction.from_dict(record)

        self.assertEqual(transaction.memo, "")
        self.assertEqual(transaction.tags, [])

    def test_from_dict_rejects_missing_required_field(self) -> None:
        for field in ["id", "type", "date", "amount", "category"]:
            record = {k: v for k, v in VALID_RECORD.items() if k != field}
            with self.subTest(missing=field):
                with self.assertRaises(BudgetAppError):
                    Transaction.from_dict(record)

    def test_from_dict_rejects_wrong_values(self) -> None:
        wrong_values: list[tuple[str, Any]] = [
            ("id", "12"),
            ("id", 12),
            ("type", "gift"),
            ("date", "2024-02-30"),
            ("date", 20240115),
            ("amount", True),
            ("amount", "15000"),
            ("amount", 0),
            ("amount", 1.5),
            ("category", ""),
            ("category", 1),
            ("memo", 1),
            ("tags", "meal"),
            ("tags", [1]),
        ]
        for field, value in wrong_values:
            with self.subTest(field=field, value=value):
                with self.assertRaises(BudgetAppError):
                    Transaction.from_dict({**VALID_RECORD, field: value})

    def test_from_dict_rejects_non_object_record(self) -> None:
        with self.assertRaises(BudgetAppError):
            Transaction.from_dict([1, 2])  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
