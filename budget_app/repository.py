import json
from pathlib import Path
from typing import Any, Iterator

from budget_app.errors import BudgetAppError
from budget_app.models import Transaction


def _damaged_line(path: Path, line_number: int) -> BudgetAppError:
    return BudgetAppError(
        f"{path.name} 파일의 {line_number}번째 줄이 손상되었습니다.",
        "저장 파일의 해당 줄을 고치거나 지운 뒤 다시 실행하세요.",
    )


def read_jsonl(path: Path) -> Iterator[tuple[int, dict[str, Any]]]:
    """파일 전체를 올리지 않고 줄 번호와 내용을 한 줄씩 돌려준다."""
    with path.open(encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            try:
                record = json.loads(line)
            except json.JSONDecodeError as error:
                raise _damaged_line(path, line_number) from error
            if not isinstance(record, dict):
                raise _damaged_line(path, line_number)
            yield line_number, record


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record, ensure_ascii=False) + "\n")


class CategoryStore:
    """카테고리 파일을 읽고 쓴다."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def list_all(self) -> list[str]:
        names = []
        for line_number, record in read_jsonl(self.path):
            name = record.get("name")
            if not isinstance(name, str) or not name:
                raise _damaged_line(self.path, line_number)
            names.append(name)
        return names

    def add(self, name: str) -> None:
        append_jsonl(self.path, {"name": name})


class TransactionRepository:
    """거래 파일을 읽고 쓰는 책임만 맡는다. 업무 규칙은 서비스가 맡는다."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def iter_all(self) -> Iterator[Transaction]:
        for line_number, record in read_jsonl(self.path):
            try:
                yield Transaction.from_dict(record)
            except BudgetAppError as error:
                raise _damaged_line(self.path, line_number) from error

    def append(self, transaction: Transaction) -> None:
        append_jsonl(self.path, transaction.to_dict())

    def next_id(self, offset: int = 0) -> str:
        """파일을 끝까지 읽어 가장 큰 번호 다음의 id를 돌려준다."""
        largest = max((tx.id_number for tx in self.iter_all()), default=0)
        return f"TX-{largest + 1 + offset:06d}"
