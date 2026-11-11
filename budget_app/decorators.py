import argparse
import sys
from datetime import datetime
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
            print(file=sys.stderr)  # 끊긴 입력 줄에 붙지 않도록 줄을 바꾼다.
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


def _write_log(args: argparse.Namespace, result: str) -> None:
    """시각, 명령, 결과만 남긴다. 기록에 실패해도 명령은 계속 진행한다."""
    command = args.command
    if hasattr(args, "action"):
        command = f"{command} {args.action}"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with (args.data_dir / "app.log").open("a", encoding="utf-8") as file:
            file.write(f"{timestamp} {command} {result}\n")
    except OSError:
        pass


def log_execution(func: Handler) -> Handler:
    """명령의 성공과 실패를 기록한다. 오류는 handle_errors가 처리하도록 다시 던진다."""

    @wraps(func)
    def wrapper(args: argparse.Namespace) -> int:
        try:
            result = func(args)
        except BaseException:
            _write_log(args, "실패")
            raise
        _write_log(args, "성공")
        return result

    return wrapper
