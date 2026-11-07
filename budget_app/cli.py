import argparse
import sys
from pathlib import Path
from typing import NoReturn

PROG = "python3 -m budget_app"


class BudgetArgumentParser(argparse.ArgumentParser):
    """잘못된 옵션을 [오류]와 [힌트] 형식으로 출력하는 파서."""

    def error(self, message: str) -> NoReturn:
        print(f"[오류] {message}", file=sys.stderr)
        print(f"[힌트] {self.prog} --help 로 사용법을 확인하세요.", file=sys.stderr)
        sys.exit(2)


def build_parser() -> argparse.ArgumentParser:
    parser = BudgetArgumentParser(prog=PROG, description="나만의 용돈 기입장")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data"),
        help="저장 폴더 (기본값: ./data)",
    )
    parser.add_subparsers(dest="command", required=True, metavar="<command>")
    return parser


def main(argv: list[str] | None = None) -> int:
    build_parser().parse_args(argv)
    return 0
