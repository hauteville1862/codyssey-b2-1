import heapq
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from budget_app.errors import BudgetAppError
from budget_app.models import Transaction
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

    def iter_matching(self, filters: SearchFilters) -> Iterator[Transaction]:
        """조건에 맞는 거래를 한 건씩 돌려주는 제너레이터."""
        return self.transactions.iter_all()

    def search(self, filters: SearchFilters, limit: int = 20) -> list[Transaction]:
        """파일을 끝까지 읽되, 메모리에는 최신 거래 limit건만 유지한다."""
        return heapq.nlargest(
            limit,
            self.iter_matching(filters),
            key=lambda tx: (tx.date, tx.id_number),
        )
