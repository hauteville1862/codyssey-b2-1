import tempfile
import unittest
from pathlib import Path

from budget_app.errors import BudgetAppError
from budget_app.services import BudgetService


class ServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        self.data_dir = Path(temp_dir.name) / "data"
        self.service = BudgetService(self.data_dir)


class CategoryServiceTest(ServiceTestCase):
    def test_empty_category_file_gets_default_categories(self) -> None:
        self.assertEqual(
            self.service.categories.list_all(),
            ["food", "transport", "rent", "etc", "salary"],
        )

    def test_add_category_trims_spaces_and_keeps_it(self) -> None:
        self.assertEqual(self.service.add_category(" pet "), "pet")

        self.assertIn("pet", BudgetService(self.data_dir).categories.list_all())

    def test_add_category_rejects_empty_and_duplicate_names(self) -> None:
        for name in ["", "   ", "food"]:
            with self.subTest(name=name):
                with self.assertRaises(BudgetAppError):
                    self.service.add_category(name)

    def test_damaged_category_line_reports_line_number(self) -> None:
        (self.data_dir / "categories.jsonl").write_text(
            '{"name": "food"}\n{"wrong": 1}\n', encoding="utf-8"
        )

        with self.assertRaises(BudgetAppError) as caught:
            self.service.categories.list_all()

        self.assertIn("2번째 줄", caught.exception.message)


class AddTransactionTest(ServiceTestCase):
    def test_add_transaction_assigns_increasing_ids(self) -> None:
        first = self.service.add_transaction(
            "expense", "2024-01-15", 15000, "food", "점심", ["meal"]
        )
        second = self.service.add_transaction(
            "income", "2024-01-16", 3000000, "salary", "", []
        )

        self.assertEqual(first.id, "TX-000001")
        self.assertEqual(second.id, "TX-000002")
        self.assertEqual(list(self.service.transactions.iter_all()), [first, second])

    def test_add_transaction_rejects_unregistered_category(self) -> None:
        with self.assertRaises(BudgetAppError) as caught:
            self.service.add_transaction("expense", "2024-01-15", 1000, "nope", "", [])

        self.assertIn("food", caught.exception.hint)
        self.assertEqual(list(self.service.transactions.iter_all()), [])


if __name__ == "__main__":
    unittest.main()
