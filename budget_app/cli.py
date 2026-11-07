import argparse
import sys
from pathlib import Path
from typing import Callable, NoReturn, TypeVar

from budget_app.decorators import handle_errors, report_error
from budget_app.errors import BudgetAppError
from budget_app.models import (
    Transaction,
    parse_amount,
    parse_date,
    parse_tags,
    parse_type,
)
from budget_app.services import BudgetService, SearchFilters

PROG = "python3 -m budget_app"

T = TypeVar("T")


class BudgetArgumentParser(argparse.ArgumentParser):
    """잘못된 옵션을 [오류]와 [힌트] 형식으로 출력하는 파서."""

    def error(self, message: str) -> NoReturn:
        print(f"[오류] {message}", file=sys.stderr)
        print(f"[힌트] {self.prog} --help 로 사용법을 확인하세요.", file=sys.stderr)
        sys.exit(2)


def ask(prompt: str, parse: Callable[[str], T]) -> T:
    """올바른 값을 입력할 때까지 다시 묻는다."""
    while True:
        try:
            return parse(input(prompt))
        except BudgetAppError as error:
            report_error(error.message, error.hint)


@handle_errors
def cmd_add(args: argparse.Namespace) -> int:
    service = BudgetService(args.data_dir)
    transaction = service.add_transaction(
        date=ask("날짜(YYYY-MM-DD): ", parse_date),
        tx_type=ask("타입(income/expense): ", parse_type),
        category=ask("카테고리: ", service.require_category),
        amount=ask("금액(양수): ", parse_amount),
        memo=input("메모(선택): "),
        tags=parse_tags(input("태그(쉼표로 구분, 없으면 엔터): ")),
    )
    print(f"[저장 완료] id={transaction.id}")
    return 0


def format_transaction(tx: Transaction) -> str:
    fields = [tx.id, tx.date, tx.type, tx.category, tx.amount, tx.memo, ",".join(tx.tags)]
    return " | ".join(str(field) for field in fields)


@handle_errors
def cmd_list(args: argparse.Namespace) -> int:
    transactions = BudgetService(args.data_dir).search(SearchFilters(), args.limit)
    if not transactions:
        print("거래 내역이 없습니다.")
    for transaction in transactions:
        print(format_transaction(transaction))
    return 0


@handle_errors
def cmd_category_list(args: argparse.Namespace) -> int:
    for name in BudgetService(args.data_dir).categories.list_all():
        print(f"- {name}")
    return 0


@handle_errors
def cmd_category_add(args: argparse.Namespace) -> int:
    service = BudgetService(args.data_dir)
    name = service.add_category(input("카테고리명: "))
    print(f"[저장 완료] category={name}")
    return 0


def positive_int(value: str) -> int:
    """--limit, --top의 값을 검사한다. 잘못되면 argparse가 사용법 오류로 처리한다."""
    try:
        return parse_amount(value)
    except BudgetAppError as error:
        raise argparse.ArgumentTypeError("1 이상의 정수여야 합니다.") from error


def build_parser() -> argparse.ArgumentParser:
    parser = BudgetArgumentParser(prog=PROG, description="나만의 용돈 기입장")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data"),
        help="저장 폴더 (기본값: ./data)",
    )
    commands = parser.add_subparsers(dest="command", required=True, metavar="<command>")

    commands.add_parser("add", help="거래 추가 (대화형)").set_defaults(handler=cmd_add)

    list_parser = commands.add_parser("list", help="거래 목록 (최신순)")
    list_parser.add_argument(
        "--limit", type=positive_int, default=20, help="출력 개수 (기본값: 20)"
    )
    list_parser.set_defaults(handler=cmd_list)

    category = commands.add_parser("category", help="카테고리 관리")
    actions = category.add_subparsers(dest="action", required=True, metavar="<action>")
    actions.add_parser("list", help="카테고리 목록").set_defaults(
        handler=cmd_category_list
    )
    actions.add_parser("add", help="카테고리 추가 (대화형)").set_defaults(
        handler=cmd_category_add
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.handler(args)
