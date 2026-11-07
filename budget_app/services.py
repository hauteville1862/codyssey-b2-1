from pathlib import Path

from budget_app.errors import BudgetAppError
from budget_app.repository import CategoryStore, TransactionRepository

DEFAULT_CATEGORIES = ("food", "transport", "rent", "etc", "salary")


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
