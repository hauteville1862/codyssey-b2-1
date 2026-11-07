# codyssey-b2-1

나만의 용돈 기입장. 수입과 지출을 파일에 저장하고 조회, 검색, 월별 요약, 예산 경고, CSV 가져오기와 내보내기를 제공하는 콘솔 프로그램입니다.

## 실행 방법

Python 3.10 이상이 필요합니다. 표준 라이브러리만 쓰므로 설치할 것은 없습니다. 프로젝트 폴더에서 실행합니다.

```bash
python3 --version
python3 -m budget_app --help
python3 -m budget_app search --help
```

저장 폴더를 바꾸려면 명령 앞에 `--data-dir`을 씁니다.

```bash
python3 -m budget_app --data-dir ./demo-data list
```

테스트는 다음 명령으로 실행합니다.

```bash
python3 -m unittest discover -s tests -v
```

## 저장 파일

기본 저장 폴더는 `./data`이며, 명령을 실행할 때 폴더와 파일이 없으면 자동으로 만듭니다. 데이터 파일의 형식은 JSONL(한 줄에 JSON 객체 하나)입니다.

| 파일 | 내용 | 한 줄의 예 |
|---|---|---|
| `transactions.jsonl` | 거래 | `{"id": "TX-000001", "type": "expense", "date": "2024-01-15", "amount": 15000, "category": "food", "memo": "점심", "tags": ["meal"]}` |
| `categories.jsonl` | 카테고리 | `{"name": "food"}` |
| `budgets.jsonl` | 월별 예산 | `{"month": "2024-01", "amount": 500000}` |
| `app.log` | 실행 기록(일반 텍스트). 시각, 명령, 결과만 남깁니다 | `2024-01-15 12:30:00 add 성공` |

## 주요 명령

아래 명령은 위에서부터 순서대로 실행할 수 있습니다. 대화형 명령은 질문에 값을 입력합니다.

```bash
# 거래 추가 (대화형)
python3 -m budget_app add

# 최신순 목록
python3 -m budget_app list --limit 5

# 조건 검색 (모든 옵션은 선택)
python3 -m budget_app search --from 2024-01-01 --to 2024-01-31 --category food --type expense --q 점심 --tag meal --limit 10

# 월 예산 저장과 월별 요약
python3 -m budget_app budget set --month 2024-01 --amount 500000
python3 -m budget_app summary --month 2024-01 --top 3

# 카테고리 관리 (add와 remove는 대화형)
python3 -m budget_app category list
python3 -m budget_app category add
python3 -m budget_app category remove

# 거래 수정과 삭제
python3 -m budget_app update --id TX-000001 --amount 20000 --memo "저녁"
python3 -m budget_app delete --id TX-000001

# CSV 가져오기와 내보내기
python3 -m budget_app import --from samples/import_ok.csv
python3 -m budget_app export --out export.csv --month 2024-01
python3 -m budget_app export --out export-period.csv --from 2024-01-01 --to 2024-01-31
```

`add`의 입력 흐름은 다음과 같습니다.

```text
$ python3 -m budget_app add
날짜(YYYY-MM-DD): 2024-01-15
타입(income/expense): expense
카테고리: food
금액(양수): 15000
메모(선택): 점심
태그(쉼표로 구분, 없으면 엔터): meal
[저장 완료] id=TX-000001
```

## 고정한 동작

- **옵션 표기:** `--`로 통일합니다.
- **입력 방식:** `add`, `category add`, `category remove`는 대화형이고, 나머지는 옵션 방식입니다.
- **`update`:** 옵션 방식으로 고정합니다. `--id`와 함께 `--date`, `--type`, `--category`, `--amount`, `--memo`, `--tags` 중 하나 이상을 줍니다. `--memo ""`와 `--tags ""`는 값을 비웁니다.
- **기본 카테고리:** 카테고리 파일이 비어 있으면 `food`, `transport`, `rent`, `etc`, `salary`를 자동으로 만듭니다.
- **카테고리 삭제:** 사용 중인 카테고리는 삭제할 수 없습니다. 거래를 다른 카테고리로 옮긴 뒤 삭제합니다.
- **`list`, `search`:** 날짜 내림차순, 같은 날짜는 id 내림차순으로 기본 20건을 보여 줍니다. `search`는 결과가 개수만큼 차면 안내 문구를 출력합니다. 출력 열은 `id | date | type | category | amount | memo | tags`입니다.
- **`export`:** `--month` 또는 `--from`과 `--to`가 필요합니다. 출력 파일이 이미 있으면 덮어쓰지 않고 오류를 냅니다.
- **`import`:** 깨진 행이 하나라도 있으면 아무것도 저장하지 않고, 문제 행의 줄 번호와 이유를 모두 출력합니다. 같은 파일을 두 번 가져오면 중복으로 등록됩니다.
- **오류와 종료 코드:** 오류는 `[오류]`와 `[힌트]`로 출력합니다. 정상은 0, 처리한 오류는 1, 잘못된 옵션은 2로 끝납니다.

## import/export CSV 스키마

UTF-8 인코딩이며 첫 줄은 헤더입니다. 엑셀에서 저장한 UTF-8 CSV의 BOM도 읽을 수 있습니다. 거래 id는 CSV에 없으며, 가져올 때 새로 부여합니다.

| 컬럼 | 필수 | 설명 |
|---|---|---|
| `date` | 예 | `YYYY-MM-DD` |
| `type` | 예 | `income` 또는 `expense` |
| `category` | 예 | 등록된 카테고리 |
| `amount` | 예 | 양의 정수 |
| `memo` | 아니요 | 문자열 |
| `tags` | 아니요 | 쉼표로 구분한 문자열 |

```csv
date,type,category,amount,memo,tags
2024-01-15,expense,food,15000,"점심, 김밥","meal,lunch"
2024-01-05,income,salary,3000000,1월 월급,
```

예제 파일은 `samples/`에 있습니다. `import_ok.csv`는 정상 파일이고, `import_broken.csv`는 깨진 행이 섞인 파일입니다.
