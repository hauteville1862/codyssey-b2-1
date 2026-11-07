import csv
import json
import os
from pathlib import Path
from typing import Any, Iterable, Iterator

from budget_app.errors import BudgetAppError
from budget_app.models import Transaction, parse_amount, parse_month

CSV_COLUMNS = ("date", "type", "category", "amount", "memo", "tags")
CSV_REQUIRED_COLUMNS = ("date", "type", "category", "amount")


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


def _to_line(record: dict[str, Any]) -> str:
    return json.dumps(record, ensure_ascii=False) + "\n"


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as file:
        file.write(_to_line(record))


def atomic_write(path: Path, lines: Iterable[str]) -> None:
    """임시 파일에 다 쓴 뒤 교체한다. 도중에 실패하면 원본은 그대로 남는다."""
    temp_path = path.with_name(f"{path.name}.tmp")
    try:
        with temp_path.open("w", encoding="utf-8") as file:
            for line in lines:
                file.write(line)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temp_path, path)
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise


def read_csv_rows(path: Path) -> Iterator[tuple[int, dict[Any, Any]]]:
    """CSV를 한 행씩 돌려준다. utf-8-sig라 엑셀의 BOM도 처리된다."""
    try:
        with path.open(encoding="utf-8-sig", newline="") as file:
            reader = csv.DictReader(file)
            columns = reader.fieldnames or []
            missing = [name for name in CSV_REQUIRED_COLUMNS if name not in columns]
            if missing:
                raise BudgetAppError(
                    f"CSV에 필수 컬럼이 없습니다: {', '.join(missing)}",
                    f"헤더를 {','.join(CSV_COLUMNS)} 형식으로 맞추세요.",
                )
            for row in reader:
                yield reader.line_num, row
    except UnicodeDecodeError as error:
        raise BudgetAppError(
            "CSV 파일이 UTF-8 형식이 아닙니다.", "UTF-8로 저장한 뒤 다시 실행하세요."
        ) from error


def write_csv(path: Path, transactions: Iterable[Transaction]) -> int:
    """새 CSV 파일에 거래를 쓴다. "x" 모드라 이미 있는 파일은 덮어쓰지 않는다."""
    try:
        file = path.open("x", encoding="utf-8", newline="")
    except FileExistsError as error:
        raise BudgetAppError(
            f"이미 있는 파일입니다: {path}",
            "다른 이름을 지정하거나 기존 파일을 지운 뒤 다시 실행하세요.",
        ) from error
    count = 0
    with file:
        writer = csv.writer(file, lineterminator="\n")
        writer.writerow(CSV_COLUMNS)
        for tx in transactions:
            tags = ",".join(tx.tags)
            writer.writerow([tx.date, tx.type, tx.category, tx.amount, tx.memo, tags])
            count += 1
    return count


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

    def remove(self, name: str) -> None:
        kept = [other for other in self.list_all() if other != name]
        atomic_write(self.path, (_to_line({"name": other}) for other in kept))


class BudgetStore:
    """월별 예산 파일을 읽고 쓴다."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def _read_all(self) -> dict[str, int]:
        budgets = {}
        for line_number, record in read_jsonl(self.path):
            month, amount = record.get("month"), record.get("amount")
            try:
                if type(amount) is not int:
                    raise _damaged_line(self.path, line_number)
                budgets[parse_month(month)] = parse_amount(str(amount))
            except (BudgetAppError, TypeError) as error:
                raise _damaged_line(self.path, line_number) from error
        return budgets

    def get(self, month: str) -> int | None:
        return self._read_all().get(month)

    def set(self, month: str, amount: int) -> None:
        budgets = {**self._read_all(), month: amount}
        lines = (
            _to_line({"month": name, "amount": value}) for name, value in budgets.items()
        )
        atomic_write(self.path, lines)


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

    def find(self, tx_id: str) -> Transaction | None:
        return next((tx for tx in self.iter_all() if tx.id == tx_id), None)

    def replace_all(self, transactions: Iterable[Transaction]) -> None:
        """거래 파일 전체를 주어진 거래들로 안전하게 교체한다."""
        atomic_write(self.path, (_to_line(tx.to_dict()) for tx in transactions))

    def next_ids(self, count: int) -> list[str]:
        """파일을 끝까지 읽어 가장 큰 번호 다음의 id를 count개 돌려준다."""
        largest = max((tx.id_number for tx in self.iter_all()), default=0)
        return [f"TX-{largest + step:06d}" for step in range(1, count + 1)]

    def next_id(self) -> str:
        return self.next_ids(1)[0]
