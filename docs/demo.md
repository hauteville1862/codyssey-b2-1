# 시연 순서표

동료평가 항목 1(E01~E07)을 보여 주는 순서입니다. 프로젝트 폴더에서 위에서부터 차례대로 실행합니다. 시연 명령은 실행 스크립트 `./demo`로 줄였습니다. `./demo`는 `python3 -m budget_app --data-dir ./demo-data`를 대신 실행하므로, 시연 데이터는 `demo-data/`에만 저장되고 실제 데이터인 `data/`와 분리됩니다.

| 평가 항목 | 보여 주는 곳 |
|---|---|
| E01 add, list, search, summary, export, import, update, delete | 2, 3, 4, 6, 7절 |
| E02 재실행 후 데이터 유지, 저장 파일 3개 이상 | 1, 9절 |
| E03 category add, list, remove | 1, 5절 |
| E04 예산 저장, 사용률, 초과 경고 | 6절 |
| E05 CSV 스키마로 import, export | 2, 7절 |
| E06 오류 메시지와 해결 힌트 | 5, 7, 8절 |
| E07 오류 시 0이 아닌 종료 코드 | 5, 7, 8절 |

## 0. 준비와 초기화

```bash
python3 --version
rm -rf demo-data export.csv
cat demo
```

버전이 3.10 이상인지 봅니다. 두 번째 줄은 이전 시연의 데이터를 지웁니다. 다시 시연할 때도 여기부터 시작합니다.

세 번째 줄로 평가자에게 `./demo`가 줄인 명령을 보여 줍니다. 예를 들어 `./demo category list`는 `python3 -m budget_app --data-dir ./demo-data category list`와 같습니다.

```text
#!/bin/sh
exec python3 -m budget_app --data-dir ./demo-data "$@"
```

## 1. 첫 실행과 카테고리 (E02, E03)

```bash
./demo category list
ls demo-data
```

기대 결과: 기본 카테고리 5개가 나오고, 폴더에 `transactions.jsonl`, `categories.jsonl`, `budgets.jsonl`과 `app.log`가 있습니다.

```bash
./demo category add
```

입력: `pet`

기대 결과: `[저장 완료] category=pet`

```bash
./demo category remove
```

입력: `pet`

기대 결과: `[삭제 완료] category=pet`

## 2. 거래 추가와 가져오기 (E01, E05)

```bash
./demo add
```

| 질문 | 입력 |
|---|---|
| 날짜 | `2024-01-15` |
| 타입 | `expense` |
| 카테고리 | `food` |
| 금액 | `15000` |
| 메모 | `점심` |
| 태그 | `meal` |

기대 결과: `[저장 완료] id=TX-000001`

```bash
./demo import --from samples/import_ok.csv
./demo list --limit 3
```

기대 결과: `[완료] imported=4, skipped=0` 다음에 아래 3건이 나옵니다. 같은 날짜는 id가 큰 거래가 위에 옵니다.

```text
TX-000005 | 2024-01-20 | expense | transport | 20000 | 교통카드 충전 | 
TX-000004 | 2024-01-15 | expense | food | 15000 | 점심, 김밥 | meal,lunch
TX-000001 | 2024-01-15 | expense | food | 15000 | 점심 | meal
```

## 3. 검색 (E01)

```bash
./demo search --from 2024-01-10 --to 2024-01-15
./demo search --category food --type expense
./demo search --q 점심
./demo search --tag lunch
```

기대 결과: 차례대로 3건(`TX-000004`, `TX-000001`, `TX-000003`), 2건(`TX-000004`, `TX-000001`), 2건(`TX-000004`, `TX-000001`), 1건(`TX-000004`)입니다.

## 4. 수정과 삭제 (E01)

```bash
./demo update --id TX-000001 --amount 20000 --memo "저녁"
./demo delete --id TX-000005
./demo list
```

기대 결과: `[수정 완료] id=TX-000001`, `[삭제 완료] id=TX-000005` 다음에 아래 4건이 나옵니다.

```text
TX-000004 | 2024-01-15 | expense | food | 15000 | 점심, 김밥 | meal,lunch
TX-000001 | 2024-01-15 | expense | food | 20000 | 저녁 | meal
TX-000003 | 2024-01-10 | expense | rent | 150000 | 월세 | 
TX-000002 | 2024-01-05 | income | salary | 3000000 | 1월 월급 | 
```

## 5. 사용 중인 카테고리 삭제 (E03, E06, E07)

```bash
./demo category remove
echo $?
```

입력: `food`

기대 결과: `[오류] 사용 중인 카테고리는 삭제할 수 없습니다: food (2건)`, `[힌트]`, 종료 코드 `1`

## 6. 요약과 예산 (E01, E04)

```bash
./demo budget set --month 2024-01 --amount 500000
./demo summary --month 2024-01 --top 3
```

기대 결과:

```text
[저장 완료] 2024-01 예산 500000원
총 수입: 3000000원
총 지출: 185000원
잔액: 2815000원
예산: 500000원 (사용률 37.0%)
지출 TOP 3
1) rent 150000원
2) food 35000원
```

```bash
./demo budget set --month 2024-01 --amount 100000
./demo summary --month 2024-01 --top 3
./demo summary --month 2024-02
```

기대 결과: 예산 줄이 `예산: 100000원 (사용률 185.0%)`로 바뀌고 `[경고] 예산을 85000원 초과했습니다.`가 나옵니다. 마지막 명령은 `데이터 없음`을 출력합니다.

## 7. CSV 내보내기와 깨진 파일 가져오기 (E01, E05, E06, E07)

```bash
./demo export --out export.csv --month 2024-01
cat export.csv
```

기대 결과: `[완료] export.csv (4 records)` 다음에 아래 내용이 나옵니다. 거래 줄은 `list`와 달리 추가한 순서(id 순)입니다. `export`는 저장 파일을 한 줄씩 읽어 바로 쓰고, 날짜순으로 다시 정리하지 않기 때문입니다.

```text
date,type,category,amount,memo,tags
2024-01-15,expense,food,20000,저녁,meal
2024-01-05,income,salary,3000000,1월 월급,
2024-01-10,expense,rent,150000,월세,
2024-01-15,expense,food,15000,"점심, 김밥","meal,lunch"
```

```bash
./demo import --from samples/import_broken.csv
echo $?
./demo list
```

기대 결과: `[오류] 깨진 행이 있어 아무것도 가져오지 않았습니다.`, 3~7번째 줄의 이유, `[힌트]`, 종료 코드 `1`이 나옵니다. 정상 행인 2번째 줄도 저장되지 않아 목록은 4절과 같은 4건입니다.

## 8. 오류 처리와 종료 코드 (E06, E07)

아래 명령을 한 줄씩 실행하고, 바로 다음의 `echo $?`로 종료 코드를 보여 줍니다.

```bash
./demo summary --month 2024-13
echo $?
./demo delete --id TX-999999
echo $?
./demo export --out export.csv --month 2024-01
echo $?
./demo import --from samples/no_such_file.csv
echo $?
./demo list --unknown-option
echo $?
```

| 명령 | 기대 결과 | 종료 코드 |
|---|---|---|
| 없는 달의 요약 | `월 형식이 올바르지 않습니다` | 1 |
| 없는 id 삭제 | `없는 데이터입니다` | 1 |
| 이미 있는 파일로 내보내기 | `이미 있는 파일입니다` | 1 |
| 없는 파일 가져오기 | `파일을 처리하지 못했습니다` | 1 |
| 없는 옵션 | `unrecognized arguments` | 2 |

모두 `[오류]`와 `[힌트]`가 나오고 스택트레이스는 나오지 않습니다.

잘못된 입력을 다시 묻는 동작은 `add`로 보여 줍니다.

```bash
./demo add
echo $?
```

입력: `2024-13-40`을 입력해 `[오류] 날짜 형식이 올바르지 않습니다 (YYYY-MM-DD).`와 `[힌트] 예: 2024-01-15`를 본 뒤, 날짜를 다시 묻는 곳에서 `Ctrl+C`를 누릅니다.

기대 결과: `[오류] 입력이 중단되었습니다.`, `[힌트]`, 종료 코드 `1`이 나오고 거래는 저장되지 않습니다.

## 9. 재실행 후 유지 (E02)

터미널을 새로 열고 프로젝트 폴더로 이동한 뒤 실행합니다. `./demo`는 파일이므로 새 터미널에서도 그대로 쓸 수 있습니다.

```bash
./demo list --limit 1
./demo summary --month 2024-01 --top 1
./demo category list
```

기대 결과: 거래 `TX-000004`, 예산 `100000원`, 카테고리 5개가 그대로 남아 있습니다.

## 잘 안 될 때

| 증상 | 원인과 대처 |
|---|---|
| 버전이 3.10보다 낮게 나오거나, 시작할 때 `TypeError`가 남 | macOS 기본 파이썬이 실행된 경우입니다. `export PATH=/opt/homebrew/bin:$PATH`를 실행한 뒤 다시 합니다. |
| `no such file or directory: ./demo` 또는 `No module named budget_app` | 프로젝트 폴더가 아닙니다. `cd`로 이동한 뒤 다시 실행합니다. |
| `permission denied: ./demo` | 실행 권한이 없습니다. `chmod +x demo`를 실행한 뒤 다시 합니다. |
| id나 건수가 표와 다름 | 이전 시연의 데이터가 남았거나 순서가 달라진 경우입니다. 0절부터 다시 합니다. |
| 7절에서 `이미 있는 파일입니다` | 이전 `export.csv`가 남은 경우입니다. 0절부터 다시 합니다. 8절에서 나오는 것은 의도한 동작입니다. |
| 시연 중 순서가 꼬임 | 0절의 초기화 후 다시 시작합니다. 시연 데이터만 지우므로 `data/`는 그대로입니다. |
