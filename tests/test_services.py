import tempfile
import unittest
from pathlib import Path
from typing import Optional

from budget_app.errors import BudgetAppError
from budget_app.services import BudgetService, SearchFilters


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


class RemoveCategoryTest(ServiceTestCase):
    def test_unused_category_is_removed(self) -> None:
        self.service.remove_category("rent")

        self.assertEqual(
            self.service.categories.list_all(), ["food", "transport", "etc", "salary"]
        )

    def test_category_in_use_is_blocked_with_count_and_file_stays_the_same(self) -> None:
        for _ in range(2):
            self.service.add_transaction("expense", "2024-01-01", 1, "food", "", [])
        path = self.data_dir / "categories.jsonl"
        before = path.read_bytes()

        with self.assertRaises(BudgetAppError) as caught:
            self.service.remove_category("food")

        self.assertIn("2건", caught.exception.message)
        self.assertIn("update", caught.exception.hint)
        self.assertEqual(path.read_bytes(), before)

    def test_unknown_category_is_rejected(self) -> None:
        with self.assertRaises(BudgetAppError):
            self.service.remove_category("nope")

    def test_removing_every_category_restores_defaults_on_next_run(self) -> None:
        for name in ["food", "transport", "rent", "etc", "salary"]:
            self.service.remove_category(name)

        self.assertEqual(
            BudgetService(self.data_dir).categories.list_all(),
            ["food", "transport", "rent", "etc", "salary"],
        )


class QueryTestCase(ServiceTestCase):
    def add(
        self,
        date: str,
        tx_type: str = "expense",
        category: str = "food",
        amount: int = 1000,
        memo: str = "",
        tags: Optional[list[str]] = None,
    ) -> str:
        transaction = self.service.add_transaction(
            tx_type, date, amount, category, memo, tags or []
        )
        return transaction.id


class DeleteTransactionTest(QueryTestCase):
    def transaction_ids(self) -> list[str]:
        return [tx.id for tx in self.service.transactions.iter_all()]

    def test_delete_removes_only_that_transaction(self) -> None:
        first = self.add("2024-01-01")
        second = self.add("2024-01-02")

        self.service.delete_transaction(first)

        self.assertEqual(self.transaction_ids(), [second])

    def test_unknown_id_is_rejected_and_file_stays_the_same(self) -> None:
        kept = self.add("2024-01-01")
        path = self.data_dir / "transactions.jsonl"
        before = path.read_bytes()

        with self.assertRaises(BudgetAppError):
            self.service.delete_transaction("TX-999999")

        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(self.transaction_ids(), [kept])

    def test_damaged_line_stops_delete_and_file_stays_the_same(self) -> None:
        first = self.add("2024-01-01")
        path = self.data_dir / "transactions.jsonl"
        with path.open("a", encoding="utf-8") as file:
            file.write("{broken\n")
        before = path.read_bytes()

        with self.assertRaises(BudgetAppError) as caught:
            self.service.delete_transaction(first)

        self.assertIn("2번째 줄", caught.exception.message)
        self.assertEqual(path.read_bytes(), before)


class UpdateTransactionTest(QueryTestCase):
    def test_update_changes_only_given_fields_and_keeps_id(self) -> None:
        tx_id = self.add("2024-01-01", memo="점심", tags=["meal"])
        other = self.add("2024-01-02")

        updated = self.service.update_transaction(tx_id, {"amount": "20000"})

        self.assertEqual(updated.id, tx_id)
        self.assertEqual(updated.amount, 20000)
        self.assertEqual(updated.memo, "점심")
        self.assertEqual(updated.tags, ["meal"])
        stored = {tx.id: tx for tx in self.service.transactions.iter_all()}
        self.assertEqual(stored[tx_id].amount, 20000)
        self.assertEqual(stored[other].amount, 1000)

    def test_update_can_change_every_field(self) -> None:
        tx_id = self.add("2024-01-01")

        updated = self.service.update_transaction(
            tx_id,
            {
                "date": "2024-02-02",
                "type": "income",
                "category": "salary",
                "amount": "5",
                "memo": "보너스",
                "tags": "a, b",
            },
        )

        self.assertEqual(updated.date, "2024-02-02")
        self.assertEqual(updated.type, "income")
        self.assertEqual(updated.category, "salary")
        self.assertEqual(updated.amount, 5)
        self.assertEqual(updated.memo, "보너스")
        self.assertEqual(updated.tags, ["a", "b"])

    def test_empty_memo_and_tags_clear_the_values(self) -> None:
        tx_id = self.add("2024-01-01", memo="점심", tags=["meal"])

        updated = self.service.update_transaction(tx_id, {"memo": "", "tags": ""})

        self.assertEqual(updated.memo, "")
        self.assertEqual(updated.tags, [])

    def test_invalid_updates_are_rejected_and_file_stays_the_same(self) -> None:
        tx_id = self.add("2024-01-01")
        path = self.data_dir / "transactions.jsonl"
        before = path.read_bytes()
        wrong: list[tuple[str, dict[str, str]]] = [
            ("TX-999999", {"amount": "5"}),
            (tx_id, {}),
            (tx_id, {"date": "2024-02-30"}),
            (tx_id, {"type": "gift"}),
            (tx_id, {"amount": "0"}),
            (tx_id, {"category": "nope"}),
        ]
        for target, changes in wrong:
            with self.subTest(target=target, changes=changes):
                with self.assertRaises(BudgetAppError):
                    self.service.update_transaction(target, changes)
                self.assertEqual(path.read_bytes(), before)


class SearchConditionTest(QueryTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.lunch = self.add("2024-01-10", memo="회사 Lunch", tags=["meal"])
        self.bus = self.add("2024-01-31", category="transport", tags=["mealtime"])
        self.pay = self.add("2024-02-01", tx_type="income", category="salary")

    def found_ids(self, **conditions: str) -> list[str]:
        result = self.service.search(SearchFilters(**conditions))
        return [tx.id for tx in result]

    def test_period_includes_both_boundary_dates(self) -> None:
        self.assertEqual(
            self.found_ids(date_from="2024-01-10", date_to="2024-01-31"),
            [self.bus, self.lunch],
        )

    def test_month_selects_only_that_month(self) -> None:
        self.assertEqual(self.found_ids(month="2024-02"), [self.pay])

    def test_category_and_type_select_exact_values(self) -> None:
        self.assertEqual(self.found_ids(category="transport"), [self.bus])
        self.assertEqual(self.found_ids(type="income"), [self.pay])

    def test_q_matches_part_of_memo_ignoring_case(self) -> None:
        self.assertEqual(self.found_ids(q="lunch"), [self.lunch])

    def test_tag_must_match_whole_tag(self) -> None:
        self.assertEqual(self.found_ids(tag="meal"), [self.lunch])

    def test_conditions_are_combined_with_and(self) -> None:
        self.assertEqual(self.found_ids(category="food", type="income"), [])

    def test_invalid_condition_values_are_rejected(self) -> None:
        wrong: list[dict[str, str]] = [
            {"date_from": "abc"},
            {"date_to": "2024-02-30"},
            {"month": "2024-13"},
            {"type": "gift"},
            {"date_from": "2024-02-01", "date_to": "2024-01-01"},
        ]
        for conditions in wrong:
            with self.subTest(conditions=conditions):
                with self.assertRaises(BudgetAppError):
                    SearchFilters(**conditions)


class SearchNewestFirstTest(QueryTestCase):
    def test_older_date_added_later_is_ordered_by_date(self) -> None:
        march = self.add("2024-03-01")
        january = self.add("2024-01-15")

        result = self.service.search(SearchFilters())

        self.assertEqual([tx.id for tx in result], [march, january])

    def test_same_date_orders_by_id_number_descending(self) -> None:
        first = self.add("2024-01-15")
        second = self.add("2024-01-15")

        result = self.service.search(SearchFilters())

        self.assertEqual([tx.id for tx in result], [second, first])

    def test_limit_keeps_only_newest_transactions(self) -> None:
        for day in range(1, 6):
            self.add(f"2024-01-0{day}")

        result = self.service.search(SearchFilters(), limit=2)

        self.assertEqual([tx.date for tx in result], ["2024-01-05", "2024-01-04"])

    def test_default_limit_is_twenty(self) -> None:
        for day in range(1, 26):
            self.add(f"2024-01-{day:02d}")

        self.assertEqual(len(self.service.search(SearchFilters())), 20)


if __name__ == "__main__":
    unittest.main()
