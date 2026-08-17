# Data

홍대 지역 MVP용 식당·메뉴·재료 데이터를 수집하고 정규화하는 작업 공간입니다.

여기서는 **CSV까지만** 만듭니다. DB 적재는 백엔드의 관리 커맨드(`python manage.py import_*`)가
이 폴더의 `curated/` CSV를 읽어서 수행합니다. 그래서 이 폴더의 스크립트는 Django에 의존하지
않으며, 표준 라이브러리만 사용합니다 (백엔드 마이그레이션 머지 전에도 작업 가능).

## 폴더 구조

```
data/
├── raw/          # 원본 다운로드 (gitignore — 커밋하지 않음)
├── curated/      # 정규화된 CSV (커밋 대상, 백엔드 import 입력)
├── mappings/     # 코드 매핑표 (커밋 대상)
├── scripts/      # 수집·정규화·검증 스크립트 (표준 라이브러리만)
└── SCHEMA.md     # 전체 CSV 컬럼 정의 + enum 값
```

## 작업 흐름

```
1. raw/ 에 원본 다운로드        (LOCALDATA, 식약처, 레시피 데이터)
2. scripts/ 로 필터링·정규화    → curated/*.csv
3. scripts/validate.py 로 검증  → 통과해야 커밋
4. (백엔드 머지 후) manage.py import_* 로 DB 적재
```

## 스크립트

```bash
# CSV 검증 — 수집 작업 중 수시로 돌리세요
python3 data/scripts/validate.py

# 식당 후보 추출 (서울 열린데이터광장 API, 매일 갱신)
python3 data/scripts/filter_localdata.py --api \
    --out data/review/candidates.csv --top 70
#   → 사람이 _keep=y / key / name 을 채운 뒤
python3 data/scripts/filter_localdata.py --promote data/review/candidates.csv \
    --out data/curated/restaurants.csv

# 정밀레시피 hwpx → 조리 패턴
python3 data/scripts/parse_hwpx.py --dry-run          # 미매칭 재료 먼저 확인
python3 data/scripts/parse_hwpx.py \
    --out-patterns data/curated/dish_patterns.csv \
    --out-ingredients data/curated/pattern_ingredients.csv

# 식품안전나라 레시피 DB 수집
python3 data/scripts/fetch_foodsafety.py

# 알레르겐 롤업 미리보기 — 데이터가 상식적인지 눈으로 확인
python3 data/scripts/rollup_preview.py 김치볶음밥 순댓국밥
python3 data/scripts/rollup_preview.py --allergen shellfish
```

## 식당 데이터 출처와 좌표계

서울 열린데이터광장 `LOCALDATA_072404_MP`(마포구 일반음식점 인허가 정보)를 **API로**
받습니다. 매일 갱신(3일 전 자료 기준)되므로 폐업·신규가 반영됩니다. 정적 파일은 받는
순간부터 낡기 때문에 쓰지 않습니다.

좌표는 **중부원점TM(EPSG:5174)** 이며 위경도는 제공되지 않습니다 — 공식 명세서에 명시된
사항입니다. `pyproj` 로 WGS84 변환 후 저장합니다.

```bash
pip install pyproj
```

이용허락조건은 공공누리 1유형(출처표시, 상업적 이용·변경 가능)입니다.

## MVP 식당 선별 기준

방문자수·매출 필드가 원본에 없어 다음으로 대체했습니다.

- **범위** 홍대입구역 반경 800m — 외국인 관광객 밀집 구역
- **랭킹** 시설총규모(영업장 면적) 내림차순 — 좌석 수 ∝ 방문자 수용량.
  100% 채워진 유일한 정량 필드
- **제외** 업태가 '한식'이어도 상호에 주류·카페·타국 음식 키워드가 있으면 제외
  (`--show-excluded` 로 전부 확인 가능)
- **최종 확정은 사람** — 업태 분류가 부정확해 자동 필터만으로는 걸러지지 않습니다

## 수집 대상 3종

| 소스                       | 산출물                                                     | 방법                            |
| -------------------------- | ---------------------------------------------------------- | ------------------------------- |
| 공공 식품·알레르겐 데이터 | `curated/ingredients.csv`, `ingredient_allergens.csv`  | 다운로드 → 매핑표 적용         |
| 공개 한식 레시피           | `curated/dish_patterns.csv`, `pattern_ingredients.csv` | 다운로드 → 재료명 정규화       |
| 공개 식당 + 메뉴 (홍대)    | `curated/restaurants.csv`, `menus.csv`                 | 식당=LOCALDATA 자동 / 메뉴=수기 |

**메뉴는 어떤 공개 API에서도 제공되지 않습니다.** 수기 수집이 유일한 경로입니다.

## 롤업 규칙 (백엔드 계약)

CSV 를 DB 에 넣은 뒤 메뉴별 알레르겐을 계산할 때 백엔드가 따라야 하는 규칙입니다.
`rollup_preview.py --menus` 가 같은 규칙으로 구현되어 있으니 결과를 대조하세요.

**1) 재료 구성: 패턴 상속 → 메뉴 보정 순서**

```
menus.pattern_key 의 pattern_ingredients 를 그대로 물려받음
  → menu_ingredients 의 action=add 로 덮어쓰기 (같은 재료면 presence 교체)
  → action=remove 로 상속분 제거   (예: 야채비빔밥에서 소고기 제외)
```

**2) 알레르겐 강도: presence 가 likelihood 의 상한**

```
presence always    → likelihood 상한 confirmed
         usually   →              likely
         sometimes →              possible
         optional / removable →   possible

실효 likelihood = min(재료의 likelihood, presence 상한)
```

"가끔 들어가는 재료에 확실히 있는 알레르겐"은 결국 "가능" 수준입니다.
한 메뉴에서 같은 알레르겐이 여러 재료로 잡히면 **가장 강한 것**을 취하고,
근거가 된 재료를 사용자에게 함께 보여줘야 합니다.

## 출처 관리 원칙

모든 행에 `source_status` 와 `source_url` 을 남깁니다. 이 값이 사용자 분석 화면의
판정 강도에 그대로 반영되므로, 비워두지 말고 최소 `unverified` 라도 명시하세요.

이 데이터는 공개 정보와 일반적인 조리 패턴에 기반한 것이며, 식당의 실제 조리법을
검증하거나 보증하지 않습니다.
