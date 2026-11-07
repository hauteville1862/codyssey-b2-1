# B2-1 용돈기입장 기획서

> 이 문서는 코딩 승인이 아니다. 코딩은 사용자가 명시적으로 지시한 뒤 시작한다. 요구사항의 정본은 `codyssey/`의 미션 상세와 평가기준이며, 이 문서는 이를 바꾸거나 완화하지 않는다.

**목표:** 미션 상세의 필수 기능을 모두 갖춘 콘솔 가계부 `budget_app`을 만들고, 사용자가 평가 항목 E01~E16마다 자신의 언어로 답변을 쓸 수 있는 상태로 넘긴다.

**구조:** `__main__` → `cli` → `services` → `repository` 방향으로 호출한다. `models`와 `errors`는 필요한 모듈이 직접 가져다 쓰며 위 계층을 가져오지 않는다. `decorators`는 `cli`에 적용하며 `cli`와 `services`를 가져오지 않는다. 데이터는 JSONL 파일 세 개에 저장하고, 조회는 제너레이터 하나를 공유해 한 줄씩 읽는다.

**기술:** Python 3.10 이상, 표준 라이브러리만 사용, 테스트는 `unittest`.

**실행 방식:** 에이전트 한 명이 단계를 순서대로 진행한다. 병렬 작업과 서브에이전트 구현은 쓰지 않는다.

**설계 기준:** 미션 요구사항을 충족하는 가장 짧고 간결한 코드, 초보자가 자신의 말로 설명할 수 있는 코드.

## 1. 성공의 모습

- **사용자 결정:** 동료평가 전에 모든 평가 항목에 대해 자신의 언어로 쓴 마크다운 답변을 준비한다.
- **사용자 우려:** 항목 1(E01~E07)에서 실제 동작을 보여 주는 시연이 가장 걱정된다.
- **실패의 모습:** 기능은 돌아가지만 사용자가 왜 그렇게 만들었는지 설명하지 못하는 코드.

**하지 않는 것:** 보너스 과제(백업, 반복 내역, 테이블 정렬, 별도 기능으로서의 원자성 강화), 여러 프로세스의 동시 실행 대응, 외부 라이브러리, 검색용 외부 정렬, `add` 실패 시 파일 복구, 중복 id 검사.

## 2. 결정 사항

### 사용자가 결정

| 항목 | 결정 |
|---|---|
| 옵션 표기 | `--`로 통일. 미션 상세의 4-1절과 7절이 충돌해 사용자가 정했고, 코디세이의 공식 확인은 받지 않았다. |
| 저장 포맷 | JSONL |
| 빈 카테고리 파일 | 기본 카테고리 자동 생성(안 A) |
| `update` | 옵션 방식(안 A)으로 고정 |
| 사용 중 카테고리 삭제 | 차단 |
| import의 깨진 행 | 하나라도 있으면 전체 취소하고, 문제 행과 이유를 출력 |
| `update`/`delete` 저장 | 임시 파일에 쓴 뒤 교체 |
| `list`/`search` | 한 줄씩 읽으며 `heapq`로 최신 N개만 메모리에 유지 |
| `search` 기본 개수 | 20개. 결과가 20건 차면 `최대 20건 표시. 더 보려면 --limit`을 출력 |
| 데코레이터 | 예외 처리와 실행 로그 |
| 로그 | `<data-dir>/app.log`에 시각, 명령, 성공/실패만 기록. 기록에 실패해도 명령은 계속 진행 |
| 진행 방식 | 6절의 단위로 나눠 진행. 단위마다 설명과 에이전트 실행 결과 공유. 사용자 직접 실행은 18단계의 시연 순서표에서 진행 |

### 인터뷰에서 제안해 승인받음

- 기본 카테고리는 `food`, `transport`, `rent`, `etc`, `salary`다.
- 금액은 양수 정수만 받는다.
- id는 `TX-000012` 형식으로, 파일의 가장 큰 번호에 1을 더한다. 마지막 거래를 지우면 번호가 다시 쓰일 수 있다.
- 최신순은 날짜 내림차순이고, 같은 날짜는 id 내림차순이다.
- `list`의 기본 개수는 20개다.
- `--q`는 메모에서 대소문자 구분 없이 부분 일치로, `--tag`는 태그 전체 일치로 찾는다.
- 같은 달 예산을 다시 설정하면 덮어쓴다. 지출이 예산보다 많을 때만 초과 경고를 내며, 정확히 100%는 초과가 아니다.
- 미등록 카테고리가 있는 import 행은 깨진 행으로 본다. 중복 검사는 하지 않는다.
- 처리한 오류의 종료 코드는 1, 잘못된 옵션의 종료 코드는 2다.
- `data/`는 `.gitignore`에 넣는다.
- 커밋은 에이전트가 `main`에 작게 쌓고, 푸시는 사용자 승인을 받는다. 메시지 규칙은 `AGENTS.md`를 따른다.

### 기획서 검토에서 에이전트가 제안해 승인받음

**입력과 출력**
- `--data-dir`은 하위 명령 앞에 쓴다. 예: `python3 -m budget_app --data-dir ./demo-data list`
- `add`에서 잘못 입력하면 `[오류]`와 `[힌트]`를 출력하고 그 항목을 다시 묻는다.
- `category add`와 `category remove`는 대화형으로 입력받는다. 미션 상세 4-1절의 옵션 허용 목록에 없기 때문이다.
- 날짜는 `2024-01-05` 형식만 받는다. 파싱한 값을 다시 문자열로 바꿔 입력과 비교하므로 `2024-1-5`와 `2024-02-30`은 거부된다. 달도 같은 방식으로 검사한다.
- `summary`의 `--top` 기본값은 5다. `--limit`과 `--top`은 1 이상이어야 한다.
- 지출 TOP은 금액 내림차순이고, 금액이 같으면 카테고리 이름순이다.
- 거래가 없는 달에 `summary`를 실행하면 "데이터 없음"을 출력한다. 예산이 있으면 사용률 0.0%도 함께 출력한다.
- 예산 조회용 별도 명령은 만들지 않는다. 미션 상세의 출력 설명대로 `summary`에서 조회한다.
- `search`와 `export`에서 시작일이 종료일보다 늦으면 오류를 낸다.
- `update`에 바꿀 필드가 하나도 없으면 오류를 낸다. `--memo ""`와 `--tags ""`는 값을 비운다.
- 옵션으로 받은 날짜, 달, 타입, 금액도 `parse_*` 함수로 검증한다. 명령 처리 함수 안에서 검증해 오류를 `handle_errors`가 처리하게 한다.
- 성공 메시지와 건수 출력은 미션 상세 8절 예시의 형식을 따른다. 예: `[저장 완료] id=TX-000012`, `[완료] imported=5, skipped=0`
- `list`와 `search`의 출력은 미션 상세 8절 예시의 6개 열 뒤에 태그 열을 더한다. `--tag` 검색 결과를 화면에서 확인하기 위한 에이전트 판단이며, 사용자가 별도로 승인하지는 않았다.

**export와 import**
- `export`의 `--from`과 `--to`는 둘 다 있어야 한다. `--month`와 함께 주면 모든 조건을 만족하는 거래만 내보낸다.
- `export`의 출력 파일이 이미 있으면 오류를 내고 덮어쓰지 않는다. 파일을 `"x"` 모드로 열어 저장 파일과 기존 CSV를 함께 보호한다. 내보내는 도중 실패하면 새 파일에 일부만 남을 수 있으며, 그 파일을 지우고 다시 실행한다. 조건에 맞는 거래가 없으면 헤더만 있는 파일을 만든다.
- import할 CSV는 한 번만 읽는다. `memo`, `tags` 컬럼이 없으면 빈 값으로 처리하고, 열 개수가 헤더와 다른 행은 깨진 행으로 본다.
- import는 검증한 새 거래를 메모리에 모은 뒤, 기존 거래와 함께 임시 파일에 써서 교체한다. 입력 CSV가 매우 크면 메모리를 그만큼 쓰며, 이 한계는 E15에서 설명한다.

**저장 안전**
- 명령을 실행할 때 저장 폴더와 없는 저장 파일 세 개를 만든다.
- 파일 일부를 다시 쓰는 저장은 모두 `atomic_write`를 쓴다. 거래의 수정, 삭제, import와 카테고리 삭제, 예산 저장이 해당한다.
- 거래와 카테고리 추가는 파일 끝에 한 줄을 붙이며, 쓰다 실패해도 복구하지 않는다. 불완전한 줄은 다음에 읽을 때 손상된 줄로 보고한다. 내용은 온전하고 줄바꿈만 빠진 경우는 바로 드러나지 않고, 다음 추가로 두 줄이 합쳐진 뒤 손상된 줄로 보고된다. 드문 경우이고 내용이 파일에 남아 직접 고칠 수 있으므로, 막는 코드를 넣지 않고 알려진 한계로 설명한다.
- 저장 파일의 줄은 읽을 때 JSON 문법, 필드, 타입, 값을 검증한다. 문제가 있으면 파일과 줄 번호를 알리고 작업을 중단하므로, 손상된 파일을 다른 명령이 덮어쓰지 않는다.
- 모든 카테고리를 지워 파일이 비면 다음 실행 때 기본 카테고리가 다시 생성된다.

## 3. 파일 구성

| 파일 | 책임 |
|---|---|
| `budget_app/__init__.py` | 패키지 표시. 내용 없음 |
| `budget_app/__main__.py` | `python3 -m budget_app`의 진입점 |
| `budget_app/cli.py` | 명령 정의, `input()`, 출력. 계산과 파일 입출력은 하지 않음 |
| `budget_app/services.py` | 업무 규칙: 추가, 조회, 요약, 카테고리 삭제 규칙, import 검증. `SearchFilters`와 `MonthlySummary`를 정의 |
| `budget_app/repository.py` | 거래, 카테고리, 예산의 JSONL 저장과 CSV 입출력, 임시 파일 교체 |
| `budget_app/models.py` | `Transaction`과 입력값 검증 |
| `budget_app/errors.py` | 원인과 힌트를 담는 오류 클래스 |
| `budget_app/decorators.py` | 예외 처리와 실행 로그 데코레이터. `app.log` 기록도 여기서 직접 한다 |
| `tests/` | `test_models.py`, `test_repository.py`, `test_services.py`, `test_cli.py`. 모두 임시 폴더를 데이터 폴더로 사용 |
| `samples/` | 시연용 CSV: 정상 파일과 깨진 행이 있는 파일 |
| `docs/demo.md` | 시연 순서표 |
| `README.md` | 실행 방법, 저장 파일 위치와 형식, 명령 예시, CSV 스키마 |

**저장 파일:** `transactions.jsonl`, `categories.jsonl`, `budgets.jsonl`, `app.log`. 기본 폴더는 `./data`다.

**공유하는 이름**

- `Transaction`(`dataclass`): `id: str`, `type: str`, `date: str`, `amount: int`, `category: str`, `memo: str = ""`, `tags: list[str]`(기본값 빈 목록), `to_dict() -> dict`, `from_dict(data: dict) -> Transaction`
- `BudgetAppError(message: str, hint: str)`: 프로그램이 내는 유일한 오류 클래스
- `read_jsonl(path: Path) -> Iterator[tuple[int, dict]]`: 줄 번호와 내용을 한 줄씩 돌려준다.
- `append_jsonl(path: Path, record: dict) -> None`
- `atomic_write(path: Path, lines: Iterable[str]) -> None`
- `read_csv_rows(path: Path) -> Iterator[tuple[int, dict]]`, `write_csv(path: Path, txs: Iterable[Transaction]) -> int`
- `TransactionRepository`: `iter_all() -> Iterator[Transaction]`, `append(tx) -> None`, `next_id() -> str`, `next_ids(count: int) -> list[str]`, `find(tx_id) -> Transaction | None`, `replace_all(txs: Iterable[Transaction]) -> None`
- `CategoryStore`: `list_all() -> list[str]`, `add(name) -> None`, `remove(name) -> None`
- `BudgetStore`: `get(month) -> int | None`, `set(month, amount) -> None`
- `SearchFilters`(`dataclass`): `month`, `date_from`, `date_to`, `category`, `type`, `q`, `tag`(모두 `str | None`, 기본값 `None`)
- `BudgetService(data_dir: Path)`: `iter_matching(filters) -> Iterator[Transaction]`, `search(filters, limit: int = 20) -> list[Transaction]`
- `MonthlySummary`(`dataclass`): `month: str`, `income: int`, `expense: int`, `balance: int`, `top: list[tuple[str, int]]`, `budget: int | None`, `usage_percent: float | None`, `has_data: bool`
- 명령 처리 함수: `(args: argparse.Namespace) -> int`

## 4. 제약 (모든 단계에 적용)

- 미션 기준은 Python 3.10 이상이다. 코드는 3.10 문법에 맞춰 쓰고, 3.11 이후에만 있는 기능을 쓰지 않는다.
- `pip install`이 필요한 라이브러리를 쓰지 않는다.
- 모든 함수의 매개변수와 반환값에 타입 힌트를 적는다. E13의 확인은 별도 도구 없이 코드로 한다. 함수 시그니처와 이를 호출하는 코드를 나란히 읽어, 입출력 약속을 설명한다.
- 실행 환경은 이미 설치된 기본 `python3`(현재 3.15.2)이며, 가상환경은 만들지 않는다. 모든 명령은 `python3`으로 실행한다. macOS 기본 `/usr/bin/python3`은 3.9.6으로 미션 기준에 미달하므로, 시연 전에 `python3 --version`을 확인한다.
- 스택트레이스를 출력하지 않고, 오류는 `[오류]`와 `[힌트]`로 출력하며, 오류 시 0이 아닌 코드로 종료한다.
- 거래 파일 전체를 메모리에 모으지 않는다. `list`/`search`는 최신 N개, `summary`는 합계만 유지하고, `export`와 재작성은 한 줄씩 처리한다.
- CSV는 UTF-8과 헤더를 쓰며, 컬럼은 `date,type,category,amount,memo,tags` 순서다.

## 5. 실패 위험 점검

테스트로 고정할 위험 상황이다. 각각 표시한 단계에서 테스트한다.

1. **저장 파일의 손상된 줄:** 문법이 깨졌거나 필드와 값이 잘못된 줄은 파일과 줄 번호를 알려 주고 종료 코드 1로 끝난다. (3, 9단계)
2. **입력 중단:** `add` 도중 Ctrl+C나 입력 종료가 오면 저장하지 않고 스택트레이스 없이 끝난다. (6단계)
3. **형식은 맞지만 없는 날짜와 달:** `2024-02-30`, `2024-13`을 거부한다. (2단계)
4. **엑셀에서 저장한 CSV:** UTF-8 BOM이 붙어 있어도 첫 컬럼을 올바르게 읽는다. (15단계)
5. **메모의 특수 문자:** 한글, 쉼표, 따옴표, 줄바꿈이 저장, 조회, export, import를 거쳐도 그대로 유지된다. (3, 15단계)

## 6. 단계별 절차

**단계마다 반복:** 무엇을 왜 만드는지 설명 → 실패하는 테스트 작성과 실패 확인 → 구현 → 테스트 통과 확인 → 에이전트가 `직접 실행` 명령을 실행해 결과 공유 → 커밋 → 다음 단계. 사용자 지시에 따라 단계 사이에 묻지 않고 이어 가며, 푸시와 사용자 터미널 실행이 필요한 지점에서 멈춘다. 사용자의 터미널에서 실행하는 것은 18단계에서 확인한다.

**단계 시작 전 점검:** 각 단계를 시작하기 전에 `git status`와 GitHub `main`의 커밋을 확인해 사용자에게 알린다. 커밋하지 않은 변경이 있으면 커밋한다. 연속 진행 중에는 푸시 여부를 단계마다 묻지 않고, 멈추는 지점에서 한꺼번에 묻는다. 푸시는 사용자가 승인할 때만 한다.

**전체 테스트 명령:** `python3 -m unittest discover -s tests -v`

**명령 등록:** 각 단계는 그 단계에서 구현하는 명령만 등록한다. 구현 전 명령용 임시 코드는 만들지 않는다.

**증거:** 사용자가 실행한 결과는 `사용자 보고`로, 에이전트가 실행한 결과는 에이전트 실행으로 구분한다.

### 구조 만들기

**0단계. 빈 폴더와 파일 구조** (E08)
- 만드는 것: 3절의 구조대로 내용 없는 폴더와 파일을 만든다. 테스트와 코드는 쓰지 않으므로 단계마다 반복하는 절차 중 설명, 사용자 확인, 커밋만 적용한다.
  - `budget_app/`: `__init__.py`, `__main__.py`, `cli.py`, `services.py`, `repository.py`, `models.py`, `errors.py`, `decorators.py`
  - `tests/`: `test_models.py`, `test_repository.py`, `test_services.py`, `test_cli.py`
  - `samples/`: `import_ok.csv`, `import_broken.csv`
  - `docs/`: `demo.md`
- 만들지 않는 것: `data/`와 저장 파일. 프로그램이 실행될 때 만들며, 미리 만들면 첫 실행 동작을 확인할 수 없다. `README.md`는 이미 있어 그대로 둔다.
- 확인: 파일 목록이 3절과 일치하고, 모든 새 파일의 크기가 0이다.
- 직접 실행: `find budget_app tests samples docs -type f`

### 기초

**1단계. 패키지 뼈대** (E08)
- 준비: `python3 --version`이 3.10 이상인지 확인
- 파일: `__main__.py`, `cli.py`, `tests/test_cli.py`, `.gitignore`에 `data/`, `__pycache__/`, `demo-data/`, `export*.csv` 추가
- 만드는 것: `build_parser() -> argparse.ArgumentParser`, `main(argv: list[str] | None = None) -> int`, `--data-dir`. 잘못된 옵션은 `[오류]`, `[힌트]`와 종료 코드 2로 처리
- 테스트: 최상위 `--help`가 종료 코드 0, 없는 옵션과 명령 없는 실행은 종료 코드 2이며 스택트레이스 없음
- 직접 실행: `python3 -m budget_app --help`

**2단계. 모델과 입력 검증** (E09, E13)
- 파일: `models.py`, `errors.py`, `tests/test_models.py`
- 만드는 것: `BudgetAppError`, `dataclass`로 만든 `Transaction`, `parse_date`, `parse_month`, `parse_type`, `parse_amount`, `parse_tags`
- 테스트: `2024-1-5`, `2024-02-30`, `2024-13`, 금액 `0`, `-1`, `1.5`, 타입 `gift`를 거부한다. 태그 `"a, b,,"`는 `["a", "b"]`가 된다. `from_dict`는 필드가 없거나 금액이 `true`이거나 id 형식이 잘못된 값을 거부한다.
- 직접 실행: 없음. 테스트 결과를 함께 읽는다.

**3단계. 거래 저장소** (E11, E14)
- 파일: `repository.py`, `tests/test_repository.py`
- 만드는 것: `read_jsonl`, `append_jsonl`, `TransactionRepository`의 `iter_all`, `append`, `next_id`
- 테스트: 저장 후 다시 읽어 같은 거래가 나온다. 빈 파일은 빈 결과다. `iter_all`은 제너레이터다. 다음 id는 `TX-000001`부터 증가하고, `next_ids(2)`는 연속된 번호 두 개를 돌려준다. 특수 문자 메모가 유지된다. 문법이 깨진 줄과 필드가 잘못된 줄은 줄 번호가 담긴 `BudgetAppError`를 낸다.
- 직접 실행: 없음. 테스트가 만든 JSONL의 모습을 함께 본다.

**4단계. 예외 처리 데코레이터** (E06, E07, E12)
- 파일: `decorators.py`, `tests/test_cli.py`
- 만드는 것: `handle_errors`. `BudgetAppError`, `OSError`, 그 외 예외, 입력 중단을 메시지와 종료 코드 1로 바꾼다. 실제 명령에는 5단계부터 적용한다.
- 테스트: 시험용 함수로, 각 예외에서 종료 코드가 1이고, `[오류]`와 `[힌트]`가 나오며, `Traceback`이 나오지 않는 것을 확인한다. 정상이면 함수의 반환값을 그대로 돌려준다.
- 직접 실행: 없음. 실제 명령이 연결되는 5단계에서 확인한다.

### 처음 이어지는 흐름

**5단계. 카테고리 저장소와 명령** (E02, E03, E06, E07)
- 파일: `repository.py`, `services.py`, `cli.py`, `tests/test_services.py`, `tests/test_cli.py`
- 만드는 것: `CategoryStore`, `BudgetService`, `category list`, `category add`. 서비스를 만들 때 저장 폴더와 없는 저장 파일 세 개를 만든다. 명령 처리 함수에 `handle_errors`를 적용한다.
- 테스트: 빈 폴더의 첫 실행에 저장 파일 세 개와 기본 카테고리 다섯 개가 생긴다. 추가한 항목이 재실행 후에도 남는다. 중복과 빈 이름을 거부한다.
- 직접 실행: 빈 폴더에서 `category list`, `category add`, 다시 `category list`. 저장 폴더 경로에 일반 파일을 지정해 오류를 일으키고 `echo $?`로 종료 코드 확인

**6단계. `add`** (E01)
- 파일: `services.py`, `cli.py`, `tests/test_services.py`, `tests/test_cli.py`
- 만드는 것: `add_transaction`. 잘못된 입력은 `[오류]`, `[힌트]` 후 그 항목을 다시 묻는다. 등록되지 않은 카테고리는 등록 목록을 함께 안내한다.
- 테스트: 표준 입력으로 정상 저장되고 id가 출력된다. 잘못된 입력 후 재입력해 저장된다. 중간에 입력이 끝나면 아무것도 저장되지 않고 종료 코드는 1이다.
- 직접 실행: `add`로 거래 두 건 추가, 저장 파일 확인

**7단계. `list`** (E01, E02, E11)
- 파일: `services.py`, `cli.py`, `tests/test_services.py`, `tests/test_cli.py`
- 만드는 것: `SearchFilters`, `iter_matching`, `search`. `heapq.nlargest`로 구현하고, 정렬 키는 날짜와 id 번호다. `list`는 조건 없는 `search`를 호출한다.
- 테스트: 나중에 입력한 과거 날짜 거래가 날짜 순서대로 나온다. 같은 날짜는 id 내림차순이다. `--limit`이 동작하고 기본은 20개다. `--limit 0`은 오류다. 빈 데이터는 안내 문구를 출력한다.
- 직접 실행: 터미널을 새로 열어 `list --limit 2`

### 조회와 변경

**8단계. `search`** (E01, E11)
- 파일: `services.py`, `cli.py`, `tests/test_services.py`, `tests/test_cli.py`
- 만드는 것: `iter_matching`의 조건 검사, `search` 명령
- 테스트: 조건별 검색과 복합 조건, 최신순 출력, 대소문자 구분 없는 `--q`, 정확히 일치하는 `--tag`, 시작일이 종료일보다 늦으면 오류. `--from abc`, `--to 2024-02-30`, `--type gift`는 오류다. 기본 20개와 `--limit`이 동작하고, 결과가 개수만큼 차면 안내 문구가 나온다.
- 직접 실행: 기간, 카테고리, 메모 키워드 검색 각 1회

**9단계. 임시 파일 교체와 `delete`** (E01, E10)
- 파일: `repository.py`, `services.py`, `cli.py`, `tests/test_repository.py`, `tests/test_services.py`
- 만드는 것: `atomic_write`, `find`, `replace_all`, `delete_transaction`. 같은 폴더의 임시 파일에 쓰고 `flush`, `os.fsync` 후 `os.replace`로 교체한다. 실패하면 임시 파일을 지운다.
- 테스트: 삭제 후 해당 거래만 사라지고 성공 메시지가 나온다. 없는 id는 종료 코드 1이고 파일이 바뀌지 않는다. 쓰기 도중 예외가 나면 원본이 그대로이고 임시 파일이 남지 않는다. 손상된 줄이 있으면 오류로 끝나고 파일이 바뀌지 않는다.
- 직접 실행: 있는 id와 없는 id를 각각 삭제, `echo $?`

**10단계. `update`** (E01, E10)
- 파일: `services.py`, `cli.py`, `tests/test_services.py`, `tests/test_cli.py`
- 만드는 것: `update_transaction(tx_id, changes) -> Transaction`. `replace_all`을 재사용한다.
- 테스트: 지정한 필드만 바뀌고 id는 유지되며 성공 메시지가 나온다. 없는 id, 잘못된 값, 미등록 카테고리, 바꿀 필드 없음은 오류다. `--memo ""`는 메모를 비운다.
- 직접 실행: `update --id <id> --amount 20000` 후 `list`

**11단계. `category remove`** (E03)
- 파일: `repository.py`, `services.py`, `cli.py`, `tests/test_services.py`, `tests/test_cli.py`
- 만드는 것: `CategoryStore.remove`, `remove_category`, 대화형 `category remove`. 사용 중이면 건수와 해결 방법을 담은 `BudgetAppError`를 낸다. `atomic_write`로 저장한다.
- 테스트: 미사용 카테고리는 삭제된다. 사용 중이면 종료 코드 1이고 파일이 바뀌지 않는다. 없는 이름은 오류다.
- 직접 실행: 사용 중 카테고리 삭제 시도, 거래를 옮긴 뒤 재시도

### 요약

**12단계. `summary`** (E01)
- 파일: `services.py`, `cli.py`, `tests/test_services.py`, `tests/test_cli.py`
- 만드는 것: `MonthlySummary`, `monthly_summary(month, top) -> MonthlySummary`. `iter_matching`으로 읽으며 합계만 유지한다.
- 테스트: 수입, 지출, 잔액, TOP N과 동점 처리, 다른 달 제외, 데이터 없는 달의 "데이터 없음", 잘못된 `--month`는 오류.
- 직접 실행: 데이터가 있는 달과 없는 달 각 1회

**13단계. 예산** (E02, E04)
- 파일: `repository.py`, `services.py`, `cli.py`, `tests/test_services.py`, `tests/test_cli.py`
- 만드는 것: `BudgetStore`, `budget set`, `summary`의 사용률과 초과 경고. `atomic_write`로 저장한다.
- 테스트: 저장 성공 메시지가 나오고 재실행 후에도 유지된다. 같은 달은 덮어쓴다. 잘못된 `--month`와 `--amount 0`은 오류다. 사용률을 소수 첫째 자리까지 출력한다. 정확히 100%는 경고가 없고 초과하면 경고한다. 예산이 없으면 예산 줄이 없다.
- 직접 실행: 예산 안쪽과 초과 상황 각 1회

### 파일 입출력

**14단계. `export`** (E01, E05)
- 파일: `repository.py`, `services.py`, `cli.py`, `tests/test_services.py`, `tests/test_cli.py`
- 만드는 것: `write_csv`, `export_csv(out, filters) -> int`. `iter_matching`을 재사용한다.
- 테스트: 헤더와 컬럼 순서가 스키마대로이고 UTF-8이다. 처리 건수가 출력된다. 조건이 없거나 `--from`만 있으면 오류다. 잘못된 `--month`와 날짜는 오류이고 파일을 만들지 않는다. 월의 첫날과 마지막 날, 기간의 경계일이 포함된다. `--month`와 기간을 함께 주면 교집합만 나온다. 출력 파일이 이미 있으면 종료 코드 1이고 그 내용이 그대로다. `--out`에 거래 저장 파일을 지정해도 원본이 그대로다. 대상이 없으면 헤더만 쓰고 0건을 출력한다.
- 직접 실행: `export --out export.csv --month <달>` 후 파일을 열어 확인

**15단계. `import`** (E01, E05, E16)
- 파일: `repository.py`, `services.py`, `cli.py`, `samples/`, `tests/test_repository.py`, `tests/test_services.py`
- 만드는 것: `read_csv_rows`, `import_csv(path) -> int`. CSV를 한 번 읽으며 모든 행을 검증하고, 문제가 없을 때만 `replace_all`로 기존 거래와 새 거래를 저장한다. 새 거래의 id는 `next_ids(count)`로 한 번에 받아 부여한다. 파일을 행마다 다시 읽지 않기 위해 사용자가 승인한 설계다. 파일은 `utf-8-sig`로 읽어 BOM을 처리하고, UTF-8이 아니면 "UTF-8로 저장하세요" 힌트와 함께 오류를 낸다. 이 단계 끝에서 모든 명령과 하위 명령(`category add/list/remove`, `budget set`)의 `--help`를 확인한다.
- 테스트: 정상 파일이 등록되고 서로 다른 새 id가 부여되며 건수가 출력된다. 모든 명령의 `--help`가 종료 코드 0이다. CP949로 저장한 CSV는 종료 코드 1이고 거래 파일이 바뀌지 않으며 힌트가 나온다. 깨진 행이 하나라도 있으면 거래 파일이 바뀌지 않고, 모든 문제 행의 번호와 이유가 나오며, 종료 코드는 1이다. 저장 중 실패해도 거래 파일이 그대로다. 필수 컬럼 누락, `memo`와 `tags` 컬럼 없음, 열 개수가 다른 행, 없는 파일, BOM, 특수 문자 메모 왕복을 확인한다.
- 직접 실행: `samples/`의 정상 파일과 깨진 파일을 각각 가져오고, 깨진 파일 뒤에 `list`로 변화가 없는지 확인

### 마무리

**16단계. 실행 로그 데코레이터** (E12)
- 파일: `decorators.py`, `cli.py`, `tests/test_cli.py`
- 만드는 것: `log_execution`. `handle_errors` 안쪽에서 실행해 성공과 실패를 기록하고, 예외는 다시 던진다.
- 테스트: 성공과 실패가 `YYYY-MM-DD HH:MM:SS 명령 결과` 형식으로 남는다. 금액과 메모가 로그에 없다. 로그를 쓸 수 없어도 명령은 성공한다.
- 직접 실행: 명령 몇 개 실행 후 `data/app.log` 확인

**17단계. `README.md`** (미션 상세 2-10)
- 내용: 실행 방법, 저장 파일 위치와 형식, 명령 예시, CSV 스키마, 고정한 동작(`update` 옵션 방식, 기본 카테고리, 사용 중 카테고리 차단, `search` 기본 20개, `export` 기존 파일 거부, import 전체 취소)
- 확인: 문서의 명령을 빈 폴더에서 그대로 실행

**18단계. 전체 점검과 시연 순서표** (E01~E07)
- 파일: `docs/demo.md`
- 내용: `--data-dir ./demo-data`로 실제 데이터와 분리한 시연 순서. 평가 항목별 명령, 기대 결과, 실패 시 대처, 재실행을 위한 초기화 방법(`demo-data/`와 이전 `export.csv` 삭제)을 담는다.
- 확인: `python3`으로 전체 테스트를 실행하고, 사용자가 순서표대로 시연을 직접 진행한다.
- 선택: 다른 환경에서 실행할 가능성이 있으면 `uv`로 Python 3.10을 받아 테스트를 한 번 실행한다. 수행 여부는 이 단계에서 사용자에게 묻는다.

**19단계. 검토와 수정** (전체)
- 내용: Codex의 읽기 전용 검토와 `code-review`를 받고, 사용자와 함께 수정 여부를 정해 고친다.
- 확인: 수정 후 전체 테스트와 시연 순서표를 다시 실행한다. AI 검토는 준비 수단이며 동료평가를 대신하지 않는다.

## 7. 코드 완성 후

코딩과 별도 단계이며, 각각 사용자의 지시로 시작한다.

1. 검증한 후보의 전체 커밋 SHA를 고정한다.
2. 다른 사람의 레포를 `reference-repos/`에 클론해 비교한다. `AGENTS.md`의 규칙을 따른다.
3. `../../harness/explanation-practice.md` 절차로 설명을 연습한다.
4. 사용자가 E01~E16 답변을 자신의 언어로 작성한다. 저장 위치와 커밋 여부는 그때 정한다. E15는 추가 구현 없이, 완성한 코드에서 병목을 찾아 설명으로 답한다.
