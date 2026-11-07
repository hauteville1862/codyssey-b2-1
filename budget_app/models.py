from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

from budget_app.errors import BudgetAppError

TRANSACTION_TYPES = ("income", "expense")
TRANSACTION_ID_PATTERN = r"TX-\d{6,}"


def _matches_format(value: str, date_format: str) -> bool:
    """파싱한 값을 다시 문자열로 바꿔 입력과 같은지 비교한다.

    strptime만 쓰면 2024-1-5처럼 0이 빠진 값도 통과하기 때문이다.
    """
    try:
        return datetime.strptime(value, date_format).strftime(date_format) == value
    except ValueError:
        return False


def parse_date(value: str) -> str:
    if not _matches_format(value, "%Y-%m-%d"):
        raise BudgetAppError(
            "날짜 형식이 올바르지 않습니다 (YYYY-MM-DD).", "예: 2024-01-15"
        )
    return value


def parse_month(value: str) -> str:
    if not _matches_format(value, "%Y-%m"):
        raise BudgetAppError("월 형식이 올바르지 않습니다 (YYYY-MM).", "예: 2024-01")
    return value


def parse_type(value: str) -> str:
    if value not in TRANSACTION_TYPES:
        raise BudgetAppError(
            "타입이 올바르지 않습니다.", "income 또는 expense를 입력하세요."
        )
    return value


def parse_amount(value: str) -> int:
    if not (value.isascii() and value.isdigit() and int(value) > 0):
        raise BudgetAppError(
            "금액은 0보다 큰 정수여야 합니다.", "쉼표 없이 숫자만 입력하세요. 예: 15000"
        )
    return int(value)


def parse_tags(value: str) -> list[str]:
    return [tag.strip() for tag in value.split(",") if tag.strip()]


@dataclass
class Transaction:
    """거래 한 건."""

    id: str
    type: str
    date: str
    amount: int
    category: str
    memo: str = ""
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Transaction:
        """저장 파일에서 읽은 값을 검증해 Transaction으로 만든다."""
        try:
            tx_id, amount = data["id"], data["amount"]
            category = data["category"]
            memo, tags = data.get("memo", ""), data.get("tags", [])
            tx_type, date = parse_type(data["type"]), parse_date(data["date"])
        except (KeyError, TypeError, AttributeError) as error:
            raise _invalid_record() from error

        has_valid_values = (
            isinstance(tx_id, str)
            and re.fullmatch(TRANSACTION_ID_PATTERN, tx_id) is not None
            and type(amount) is int
            and amount > 0
            and isinstance(category, str)
            and category != ""
            and isinstance(memo, str)
            and isinstance(tags, list)
            and all(isinstance(tag, str) for tag in tags)
        )
        if not has_valid_values:
            raise _invalid_record()
        return cls(tx_id, tx_type, date, amount, category, memo, tags)


def _invalid_record() -> BudgetAppError:
    return BudgetAppError(
        "거래 데이터의 필드가 올바르지 않습니다.", "저장 파일의 해당 줄을 확인하세요."
    )
