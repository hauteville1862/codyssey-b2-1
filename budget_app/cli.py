import argparse
import sys
from pathlib import Path
from typing import NoReturn

from budget_app.decorators import handle_errors
from budget_app.services import BudgetService

PROG = "python3 -m budget_app"


class BudgetArgumentParser(argparse.ArgumentParser):
    """잘못된 옵션을 [오류]와 [힌트] 형식으로 출력하는 파서."""

    def error(self, message: str) -> NoReturn:
        print(f"[오류] {message}", file=sys.stderr)
        print(f"[힌트] {self.prog} --help 로 사용법을 확인하세요.", file=sys.stderr)
        sys.exit(2)


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


def build_parser() -> argparse.ArgumentParser:
    parser = BudgetArgumentParser(prog=PROG, description="나만의 용돈 기입장")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data"),
        help="저장 폴더 (기본값: ./data)",
    )
    commands = parser.add_subparsers(dest="command", required=True, metavar="<command>")

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
