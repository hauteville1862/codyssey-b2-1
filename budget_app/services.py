import heapq
from dataclasses import dataclass, replace
from itertools import chain
from pathlib import Path
from typing import Any, Callable, Iterator

from budget_app.errors import BudgetAppError
from budget_app.models import (
    Transaction,
    parse_amount,
    parse_date,
    parse_month,
    parse_tags,
    parse_type,
)
from budget_app.repository import (
    BudgetStore,
    CategoryStore,
    TransactionRepository,
    read_csv_rows,
    write_csv,
)

DEFAULT_CATEGORIES = ("food", "transport", "rent", "etc", "salary")


@dataclass
class SearchFilters:
    """거래를 고르는 조건. None인 조건은 검사하지 않는다."""

    month: str | None = None
    date_from: str | None = None
    date_to: str | None = None
    category: str | None = None
    type: str | None = None
    q: str | None = None
    tag: str | None = None

    def __post_init__(self) -> None:
        if self.month is not None:
            parse_month(self.month)
        if self.date_from is not None:
            parse_date(self.date_from)
        if self.date_to is not None:
            parse_date(self.date_to)
        if self.type is not None:
            parse_type(self.type)
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise BudgetAppError(
                "시작일이 종료일보다 늦습니다.", "--from을 --to보다 빠르게 입력하세요."
            )

    def matches(self, tx: Transaction) -> bool:
        return (
            (self.month is None or tx.date.startswith(f"{self.month}-"))
            and (self.date_from is None or tx.date >= self.date_from)
            and (self.date_to is None or tx.date <= self.date_to)
            and (self.category is None or tx.category == self.category)
            and (self.type is None or tx.type == self.type)
            and (self.q is None or self.q.lower() in tx.memo.lower())
            and (self.tag is None or self.tag in tx.tags)
        )


def _parse_csv_row(row: dict[Any, Any], categories: list[str]) -> dict[str, Any]:
    """CSV 한 행을 검증해 Transaction에 넘길 값으로 바꾼다."""
    if None in row or None in row.values():
        raise BudgetAppError("열 개수가 헤더와 다릅니다.", "CSV 행을 확인하세요.")
    if row["category"] not in categories:
        raise BudgetAppError(
            f"등록되지 않은 카테고리입니다: {row['category']}", "category add로 등록하세요."
        )
    return {
        "date": parse_date(row["date"]),
        "type": parse_type(row["type"]),
        "category": row["category"],
        "amount": parse_amount(row["amount"]),
        "memo": row.get("memo", ""),
        "tags": parse_tags(row.get("tags", "")),
    }


@dataclass
class MonthlySummary:
    """한 달의 요약 결과."""

    month: str
    income: int
    expense: int
    balance: int
    top: list[tuple[str, int]]
    budget: int | None
    usage_percent: float | None
    has_data: bool

    @property
    def over_budget(self) -> int:
        """예산을 넘긴 금액. 예산이 없거나 넘지 않았으면 0이다."""
        if self.budget is None:
            return 0
        return max(0, self.expense - self.budget)


class BudgetService:
    """가계부의 업무 규칙을 맡는다. 파일 처리는 저장소에 맡긴다."""

    def __init__(self, data_dir: Path) -> None:
        data_dir.mkdir(parents=True, exist_ok=True)
        for name in ("transactions.jsonl", "categories.jsonl", "budgets.jsonl"):
            (data_dir / name).touch()
        self.transactions = TransactionRepository(data_dir / "transactions.jsonl")
        self.categories = CategoryStore(data_dir / "categories.jsonl")
        self.budgets = BudgetStore(data_dir / "budgets.jsonl")
        if not self.categories.list_all():
            for name in DEFAULT_CATEGORIES:
                self.categories.add(name)

    def list_categories(self) -> list[str]:
        return self.categories.list_all()

    def add_category(self, name: str) -> str:
        name = name.strip()
        if not name:
            raise BudgetAppError(
                "카테고리 이름이 비어 있습니다.", "한 글자 이상 입력하세요."
            )
        if name in self.categories.list_all():
            raise BudgetAppError(
                f"이미 있는 카테고리입니다: {name}",
                "category list로 목록을 확인하세요.",
            )
        self.categories.add(name)
        return name

    def remove_category(self, name: str) -> str:
        name = self.require_category(name.strip())
        in_use = sum(1 for _ in self.iter_matching(SearchFilters(category=name)))
        if in_use:
            raise BudgetAppError(
                f"사용 중인 카테고리는 삭제할 수 없습니다: {name} ({in_use}건)",
                "update --id <id> --category <다른 카테고리>로 거래를 옮긴 뒤 다시 삭제하세요.",
            )
        self.categories.remove(name)
        return name

    def require_category(self, name: str) -> str:
        categories = self.categories.list_all()
        if name not in categories:
            raise BudgetAppError(
                f"등록되지 않은 카테고리입니다: {name}",
                f"등록된 카테고리: {', '.join(categories)}",
            )
        return name

    def add_transaction(
        self,
        tx_type: str,
        date: str,
        amount: int,
        category: str,
        memo: str,
        tags: list[str],
    ) -> Transaction:
        self.require_category(category)
        transaction = Transaction(
            self.transactions.next_id(), tx_type, date, amount, category, memo, tags
        )
        self.transactions.append(transaction)
        return transaction

    def require_transaction(self, tx_id: str) -> Transaction:
        transaction = self.transactions.find(tx_id)
        if transaction is None:
            raise BudgetAppError(
                f"없는 데이터입니다: {tx_id}", "list로 거래 id를 확인하세요."
            )
        return transaction

    def delete_transaction(self, tx_id: str) -> None:
        self.require_transaction(tx_id)
        self.transactions.replace_all(
            tx for tx in self.transactions.iter_all() if tx.id != tx_id
        )

    def update_transaction(self, tx_id: str, changes: dict[str, str]) -> Transaction:
        if not changes:
            raise BudgetAppError(
                "바꿀 값이 없습니다.", "--amount처럼 바꿀 옵션을 하나 이상 입력하세요."
            )
        parsers: dict[str, Callable[[str], Any]] = {
            "date": parse_date,
            "type": parse_type,
            "category": self.require_category,
            "amount": parse_amount,
            "memo": str,
            "tags": parse_tags,
        }
        parsed = {name: parsers[name](value) for name, value in changes.items()}
        updated = replace(self.require_transaction(tx_id), **parsed)
        self.transactions.replace_all(
            updated if tx.id == tx_id else tx for tx in self.transactions.iter_all()
        )
        return updated

    def iter_matching(self, filters: SearchFilters) -> Iterator[Transaction]:
        """조건에 맞는 거래를 한 건씩 돌려주는 제너레이터."""
        for transaction in self.transactions.iter_all():
            if filters.matches(transaction):
                yield transaction

    def monthly_summary(self, month: str, top: int) -> MonthlySummary:
        """거래를 한 건씩 읽으며 합계만 유지한다."""
        income = expense = 0
        has_data = False
        spent: dict[str, int] = {}
        for transaction in self.iter_matching(SearchFilters(month=month)):
            has_data = True
            if transaction.type == "income":
                income += transaction.amount
            else:
                expense += transaction.amount
                spent[transaction.category] = (
                    spent.get(transaction.category, 0) + transaction.amount
                )
        ranked = sorted(spent.items(), key=lambda item: (-item[1], item[0]))
        budget = self.budgets.get(month)
        usage_percent = None if budget is None else round(expense / budget * 100, 1)
        return MonthlySummary(
            month=month,
            income=income,
            expense=expense,
            balance=income - expense,
            top=ranked[:top],
            budget=budget,
            usage_percent=usage_percent,
            has_data=has_data,
        )

    def set_budget(self, month: str, amount: str) -> int:
        parsed_amount = parse_amount(amount)
        self.budgets.set(parse_month(month), parsed_amount)
        return parsed_amount

    def export_csv(self, out: Path, filters: SearchFilters) -> int:
        has_period = filters.date_from is not None and filters.date_to is not None
        has_partial_period = (filters.date_from is None) != (filters.date_to is None)
        if has_partial_period or not (filters.month or has_period):
            raise BudgetAppError(
                "내보낼 조건이 부족합니다.",
                "--month YYYY-MM 또는 --from YYYY-MM-DD --to YYYY-MM-DD를 입력하세요.",
            )
        return write_csv(out, self.iter_matching(filters))

    def import_csv(self, path: Path) -> int:
        """모든 행을 먼저 검증하고, 하나라도 깨졌으면 아무것도 저장하지 않는다."""
        categories = self.categories.list_all()
        rows: list[dict[str, Any]] = []
        problems: list[str] = []
        for line_number, row in read_csv_rows(path):
            try:
                rows.append(_parse_csv_row(row, categories))
            except BudgetAppError as error:
                problems.append(f"{line_number}번째 줄: {error.message}")
        if problems:
            raise BudgetAppError(
                "깨진 행이 있어 아무것도 가져오지 않았습니다.\n" + "\n".join(problems),
                "CSV의 해당 행을 고친 뒤 파일 전체를 다시 가져오세요.",
            )
        ids = self.transactions.next_ids(len(rows))
        transactions = (Transaction(id=tx_id, **row) for tx_id, row in zip(ids, rows))
        self.transactions.replace_all(chain(self.transactions.iter_all(), transactions))
        return len(rows)

    def search(self, filters: SearchFilters, limit: int = 20) -> list[Transaction]:
        """파일을 끝까지 읽되, 메모리에는 최신 거래 limit건만 유지한다."""
        return heapq.nlargest(
            limit,
            self.iter_matching(filters),
            key=lambda tx: (tx.date, tx.id_number),
        )
