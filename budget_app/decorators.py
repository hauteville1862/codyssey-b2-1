import argparse
import sys
from functools import wraps
from typing import Callable

from budget_app.errors import BudgetAppError

Handler = Callable[[argparse.Namespace], int]


def report_error(message: str, hint: str) -> int:
    print(f"[오류] {message}", file=sys.stderr)
    print(f"[힌트] {hint}", file=sys.stderr)
    return 1


def handle_errors(func: Handler) -> Handler:
    """명령에서 난 오류를 원인과 힌트로 출력하고 종료 코드 1을 돌려준다."""

    @wraps(func)
    def wrapper(args: argparse.Namespace) -> int:
        try:
            return func(args)
        except BudgetAppError as error:
            return report_error(error.message, error.hint)
        except (KeyboardInterrupt, EOFError):
            return report_error("입력이 중단되었습니다.", "명령을 다시 실행하세요.")
        except OSError as error:
            return report_error(
                f"파일을 처리하지 못했습니다: {error}", "경로와 권한을 확인하세요."
            )
        except Exception as error:
            return report_error(
                f"예상하지 못한 오류가 발생했습니다: {error}",
                "입력값과 저장 파일을 확인한 뒤 다시 실행하세요.",
            )

    return wrapper
