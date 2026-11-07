class BudgetAppError(Exception):
    """사용자에게 보여 줄 원인(message)과 해결 힌트(hint)를 담는 오류."""

    def __init__(self, message: str, hint: str) -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint
