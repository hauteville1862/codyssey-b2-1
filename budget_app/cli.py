import argparse
import sys
from pathlib import Path
from typing import Callable, NoReturn, TypeVar

from budget_app.decorators import handle_errors, log_execution, report_error
from budget_app.errors import BudgetAppError
from budget_app.models import (
    Transaction,
    parse_amount,
    parse_date,
    parse_tags,
    parse_type,
)
from budget_app.services import BudgetService, MonthlySummary, SearchFilters

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
@log_execution
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
@log_execution
def cmd_list(args: argparse.Namespace) -> int:
    transactions = BudgetService(args.data_dir).search(SearchFilters(), args.limit)
    if not transactions:
        print("거래 내역이 없습니다.")
    for transaction in transactions:
        print(format_transaction(transaction))
    return 0


@handle_errors
@log_execution
def cmd_search(args: argparse.Namespace) -> int:
    filters = SearchFilters(
        date_from=args.date_from,
        date_to=args.date_to,
        category=args.category,
        type=args.type,
        q=args.q,
        tag=args.tag,
    )
    transactions = BudgetService(args.data_dir).search(filters, args.limit)
    if not transactions:
        print("조건에 맞는 거래가 없습니다.")
    for transaction in transactions:
        print(format_transaction(transaction))
    if len(transactions) == args.limit:
        print(f"최대 {args.limit}건 표시. 더 보려면 --limit")
    return 0


@handle_errors
@log_execution
def cmd_delete(args: argparse.Namespace) -> int:
    BudgetService(args.data_dir).delete_transaction(args.id)
    print(f"[삭제 완료] id={args.id}")
    return 0


@handle_errors
@log_execution
def cmd_update(args: argparse.Namespace) -> int:
    fields = ("date", "type", "category", "amount", "memo", "tags")
    changes = {
        name: getattr(args, name) for name in fields if getattr(args, name) is not None
    }
    BudgetService(args.data_dir).update_transaction(args.id, changes)
    print(f"[수정 완료] id={args.id}")
    return 0


@handle_errors
@log_execution
def cmd_summary(args: argparse.Namespace) -> int:
    summary = BudgetService(args.data_dir).monthly_summary(args.month, args.top)
    if not summary.has_data:
        print("데이터 없음")
        print_budget(summary)
        return 0
    print(f"총 수입: {summary.income}원")
    print(f"총 지출: {summary.expense}원")
    print(f"잔액: {summary.balance}원")
    print_budget(summary)
    print(f"지출 TOP {args.top}")
    for rank, (category, amount) in enumerate(summary.top, start=1):
        print(f"{rank}) {category} {amount}원")
    return 0


def print_budget(summary: MonthlySummary) -> None:
    if summary.budget is None:
        return
    print(f"예산: {summary.budget}원 (사용률 {summary.usage_percent:.1f}%)")
    if summary.over_budget:
        print(f"[경고] 예산을 {summary.over_budget}원 초과했습니다.")


@handle_errors
@log_execution
def cmd_budget_set(args: argparse.Namespace) -> int:
    amount = BudgetService(args.data_dir).set_budget(args.month, args.amount)
    print(f"[저장 완료] {args.month} 예산 {amount}원")
    return 0


@handle_errors
@log_execution
def cmd_export(args: argparse.Namespace) -> int:
    filters = SearchFilters(
        month=args.month, date_from=args.date_from, date_to=args.date_to
    )
    count = BudgetService(args.data_dir).export_csv(args.out, filters)
    print(f"[완료] {args.out} ({count} records)")
    return 0


@handle_errors
@log_execution
def cmd_import(args: argparse.Namespace) -> int:
    count = BudgetService(args.data_dir).import_csv(args.source)
    print(f"[완료] imported={count}, skipped=0")
    return 0


@handle_errors
@log_execution
def cmd_category_list(args: argparse.Namespace) -> int:
    for name in BudgetService(args.data_dir).list_categories():
        print(f"- {name}")
    return 0


@handle_errors
@log_execution
def cmd_category_add(args: argparse.Namespace) -> int:
    service = BudgetService(args.data_dir)
    name = service.add_category(input("카테고리명: "))
    print(f"[저장 완료] category={name}")
    return 0


@handle_errors
@log_execution
def cmd_category_remove(args: argparse.Namespace) -> int:
    service = BudgetService(args.data_dir)
    name = service.remove_category(input("삭제할 카테고리명: "))
    print(f"[삭제 완료] category={name}")
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

    search = commands.add_parser("search", help="거래 검색 (최신순)")
    search.add_argument("--from", dest="date_from", help="시작일 YYYY-MM-DD")
    search.add_argument("--to", dest="date_to", help="종료일 YYYY-MM-DD")
    search.add_argument("--category", help="카테고리")
    search.add_argument("--type", help="income 또는 expense")
    search.add_argument("--q", help="메모 키워드")
    search.add_argument("--tag", help="태그")
    search.add_argument(
        "--limit", type=positive_int, default=20, help="출력 개수 (기본값: 20)"
    )
    search.set_defaults(handler=cmd_search)

    delete = commands.add_parser("delete", help="거래 삭제")
    delete.add_argument("--id", required=True, help="거래 id")
    delete.set_defaults(handler=cmd_delete)

    update = commands.add_parser("update", help="거래 수정 (옵션 방식)")
    update.add_argument("--id", required=True, help="거래 id")
    update.add_argument("--date", help="날짜 YYYY-MM-DD")
    update.add_argument("--type", help="income 또는 expense")
    update.add_argument("--category", help="카테고리")
    update.add_argument("--amount", help="금액 (양의 정수)")
    update.add_argument("--memo", help='메모 ("" 를 주면 비움)')
    update.add_argument("--tags", help='쉼표로 구분한 태그 ("" 를 주면 비움)')
    update.set_defaults(handler=cmd_update)

    summary = commands.add_parser("summary", help="월별 요약")
    summary.add_argument("--month", required=True, help="월 YYYY-MM")
    summary.add_argument(
        "--top", type=positive_int, default=5, help="지출 상위 개수 (기본값: 5)"
    )
    summary.set_defaults(handler=cmd_summary)

    budget = commands.add_parser("budget", help="예산 관리")
    budget_actions = budget.add_subparsers(
        dest="action", required=True, metavar="<action>"
    )
    budget_set = budget_actions.add_parser("set", help="월 예산 저장")
    budget_set.add_argument("--month", required=True, help="월 YYYY-MM")
    budget_set.add_argument("--amount", required=True, help="금액 (양의 정수)")
    budget_set.set_defaults(handler=cmd_budget_set)

    export = commands.add_parser("export", help="거래를 CSV로 내보내기")
    export.add_argument("--out", type=Path, required=True, help="새로 만들 CSV 파일")
    export.add_argument("--month", help="월 YYYY-MM")
    export.add_argument("--from", dest="date_from", help="시작일 YYYY-MM-DD")
    export.add_argument("--to", dest="date_to", help="종료일 YYYY-MM-DD")
    export.set_defaults(handler=cmd_export)

    import_parser = commands.add_parser("import", help="CSV에서 거래 가져오기")
    import_parser.add_argument(
        "--from", dest="source", type=Path, required=True, help="가져올 CSV 파일"
    )
    import_parser.set_defaults(handler=cmd_import)

    category = commands.add_parser("category", help="카테고리 관리")
    actions = category.add_subparsers(dest="action", required=True, metavar="<action>")
    actions.add_parser("list", help="카테고리 목록").set_defaults(
        handler=cmd_category_list
    )
    actions.add_parser("add", help="카테고리 추가 (대화형)").set_defaults(
        handler=cmd_category_add
    )
    actions.add_parser("remove", help="카테고리 삭제 (대화형)").set_defaults(
        handler=cmd_category_remove
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.handler(args)
