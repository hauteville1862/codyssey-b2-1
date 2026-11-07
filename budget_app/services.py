import heapq
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from budget_app.errors import BudgetAppError
from budget_app.models import Transaction, parse_date, parse_month, parse_type
from budget_app.repository import CategoryStore, TransactionRepository

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


class BudgetService:
    """가계부의 업무 규칙을 맡는다. 파일 처리는 저장소에 맡긴다."""

    def __init__(self, data_dir: Path) -> None:
        data_dir.mkdir(parents=True, exist_ok=True)
        for name in ("transactions.jsonl", "categories.jsonl", "budgets.jsonl"):
            (data_dir / name).touch()
        self.transactions = TransactionRepository(data_dir / "transactions.jsonl")
        self.categories = CategoryStore(data_dir / "categories.jsonl")
        if not self.categories.list_all():
            for name in DEFAULT_CATEGORIES:
                self.categories.add(name)

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

    def iter_matching(self, filters: SearchFilters) -> Iterator[Transaction]:
        """조건에 맞는 거래를 한 건씩 돌려주는 제너레이터."""
        for transaction in self.transactions.iter_all():
            if filters.matches(transaction):
                yield transaction

    def search(self, filters: SearchFilters, limit: int = 20) -> list[Transaction]:
        """파일을 끝까지 읽되, 메모리에는 최신 거래 limit건만 유지한다."""
        return heapq.nlargest(
            limit,
            self.iter_matching(filters),
            key=lambda tx: (tx.date, tx.id_number),
        )
