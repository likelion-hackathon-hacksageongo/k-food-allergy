# CSV 스키마 정의

모든 CSV는 UTF-8(BOM 없음), 헤더 행 필수, 쉼표 구분입니다.
스프레드시트로 작업 후 `파일 > 내보내기 > CSV` 로 저장하세요.

`✅` = 필수, `⬜` = 선택(비워도 됨)

---

## 공통 enum

### `source_status` — 정보 출처 상태
사용자 분석 화면의 판정 강도에 직접 반영됩니다.

| 값 | 의미 |
|---|---|
| `official_menu` | 업소 공식 메뉴판·업소 제공 정보 |
| `public_data` | 공공 데이터 (식약처 등) |
| `public_recipe` | 공개 레시피 |
| `cooking_pattern` | 대표 조리 패턴 기반 추정 |
| `user_feedback` | 사용자 제보 (검토 승인분) |
| `unverified` | 미확인 |

### `likelihood` — 알레르겐 포함 가능성

| 값 | 의미 | 사용자 화면 |
|---|---|---|
| `confirmed` | 90% 이상 포함 확인 | 🔴 포함 확인됨 |
| `likely` | 70~80% 포함 가능성 | 🟡 확인 필요 |
| `possible` | 20~30% 포함 가능성 | 🟡 확인 필요 |
| `none` | 포함되지 않을 확률 높음 | 표시 없음 |

> 저장하는 값은 4단계지만 사용자에게는 2단계로 접힙니다. `likely` 와 `possible` 은
> 화면에서 구분되지 않으므로, 둘 중 어느 쪽인지 고민하는 데 시간을 쓰지 마세요.
> 중요한 경계는 `confirmed` 인가 아닌가입니다. (`SCHEMA_CHANGES.md` 1번)

### `presence` — 재료가 그 메뉴에 들어가는 정도
`always` · `usually` · `sometimes` · `optional` · `removable`

### `role` — 조리 맥락에서의 역할
`main` · `broth` · `sauce` · `garnish` · `side`

### `kind` — 재료 분류
`ingredient` · `broth` · `sauce` · `jang` · `garnish`

### `info_level` — 메뉴 정보의 확실성
`confirmed` · `pattern` · `insufficient`

### `allergen_key` — 알레르겐 16종 (철자 그대로)
```
shellfish, nuts, wheat, soy, egg, dairy, fish, mollusk,
peach, peanut, pork, beef, chicken, sulfites, buckwheat, tomato
```

---

## `curated/restaurants.csv`

홍대 지역 MVP 대상 식당. LOCALDATA 필터링으로 자동 생성 후 수기 보정.

| 컬럼 | 필수 | 값 | 설명 |
|---|---|---|---|
| `key` | ✅ | slug | 식당 고유 식별자. `menus.csv` 에서 참조. 예: `hongdae_sundubu` |
| `name` | ✅ | 문자열 | 영문/로마자 상호 |
| `name_ko` | ✅ | 문자열 | 한글 상호 |
| `address` | ✅ | 문자열 | 도로명 주소 |
| `latitude` | ✅ | 실수 | WGS84 위도 |
| `longitude` | ✅ | 실수 | WGS84 경도 |
| `category` | ⬜ | 문자열 | 예: `Korean - Stew`. 비우면 `Korean` |
| `description` | ⬜ | 문자열 | 한 줄 소개 |
| `source_status` | ✅ | enum | 보통 `public_data` |
| `source_url` | ⬜ | URL | 출처 링크 |
| `collected_at` | ✅ | `YYYY-MM-DD` | 수집일 |
| `collected_by` | ⬜ | 문자열 | 수집자 |
| `is_active` | ⬜ | `true`/`false` | 비우면 `true` |

---

## `curated/menus.csv`

**수기 수집 대상.** 식당당 대표 메뉴 5~8개를 권합니다.

| 컬럼 | 필수 | 값 | 설명 |
|---|---|---|---|
| `restaurant_key` | ✅ | slug | `restaurants.csv` 의 `key` 와 일치 |
| `key` | ✅ | slug | 식당 내에서 고유. 예: `seafood_sundubu` |
| `name` | ✅ | 문자열 | 영문 메뉴명 |
| `name_ko` | ✅ | 문자열 | 한글 메뉴명 (메뉴판 표기 그대로) |
| `price_krw` | ⬜ | 정수 | 원 단위. 쉼표·`원` 없이 숫자만 |
| `pattern_key` | ⬜ | slug | `dish_patterns.csv` 참조. 지정하면 재료가 자동 상속됨 |
| `info_level` | ✅ | enum | 메뉴판 확인 = `confirmed` |
| `description` | ⬜ | 문자열 | |
| `source_status` | ✅ | enum | 메뉴판 사진 기준이면 `official_menu` |
| `source_url` | ⬜ | URL | |
| `collected_at` | ✅ | `YYYY-MM-DD` | |
| `collected_by` | ⬜ | 문자열 | |
| `notes` | ⬜ | 문자열 | |

> **작업 요령**: `pattern_key` 를 채우면 그 메뉴의 기본 재료가 패턴에서 상속됩니다.
> 순두부찌개 100개를 일일이 재료 입력할 필요 없이 `pattern_key=sundubu_jjigae` 만
> 적으면 됩니다. 메뉴마다 다른 부분만 아래 `menu_ingredients.csv` 에 예외로 적습니다.

---

## `curated/menu_ingredients.csv`

패턴 상속으로 부족한 부분만 채우는 **예외/보정 레이어**. 전 메뉴를 채울 필요 없습니다.

| 컬럼 | 필수 | 값 | 설명 |
|---|---|---|---|
| `restaurant_key` | ✅ | slug | |
| `menu_key` | ✅ | slug | |
| `ingredient_key` | ✅ | slug | `ingredients.csv` 참조 |
| `presence` | ✅ | enum | 뺄 수 있으면 `removable` |
| `role` | ✅ | enum | |
| `action` | ⬜ | `add`/`remove` | 패턴 상속분을 덮어쓸 때. 비우면 `add` |
| `source_status` | ✅ | enum | |
| `notes` | ⬜ | 문자열 | |

---

## `curated/ingredients.csv`

재료 지식베이스. 식당과 무관하게 재사용됩니다.

| 컬럼 | 필수 | 값 |
|---|---|---|
| `key` | ✅ | slug |
| `name_ko` | ✅ | 한글 재료명 (대표 표기) |
| `name_en` | ✅ | 영문명 |
| `kind` | ✅ | enum |
| `notes` | ⬜ | 문자열 |

## `curated/ingredient_allergens.csv`

**여기가 알레르겐 판정의 실제 근거입니다.** "간장에는 대두·밀이 있다"를 한 번 적으면
간장을 쓰는 모든 메뉴에 전파됩니다.

| 컬럼 | 필수 | 값 |
|---|---|---|
| `ingredient_key` | ✅ | slug |
| `allergen_key` | ✅ | 16종 중 하나 |
| `likelihood` | ✅ | enum |
| `source_status` | ✅ | enum |
| `notes` | ⬜ | 문자열 |

`(ingredient_key, allergen_key)` 조합은 유일해야 합니다.

## `curated/ingredient_aliases.csv`

레시피 데이터의 자유 텍스트 재료명을 `ingredient_key` 로 붙이는 별칭표.
**미매칭 재료를 만날 때마다 여기에 추가하는 게 반복 작업의 핵심입니다.**

| 컬럼 | 필수 | 값 |
|---|---|---|
| `ingredient_key` | ✅ | slug |
| `alias` | ✅ | 전체에서 유일. 공백 제거 후 비교됨 |

---

## `curated/dish_patterns.csv` / `pattern_ingredients.csv`

공개 레시피에서 추출한 대표 조리 패턴. (레시피 수집 단계에서 생성)

**dish_patterns.csv**

| 컬럼 | 필수 | 값 |
|---|---|---|
| `key` | ✅ | slug |
| `name_ko` | ✅ | 한글 요리명 |
| `name_en` | ✅ | 영문명 |
| `description` | ⬜ | 문자열 |
| `source_status` | ✅ | 보통 `public_recipe` |
| `source_url` | ⬜ | URL |

**pattern_ingredients.csv**

| 컬럼 | 필수 | 값 |
|---|---|---|
| `pattern_key` | ✅ | slug |
| `ingredient_key` | ✅ | slug |
| `presence` | ✅ | enum |
| `role` | ✅ | enum |

---

## `mappings/allergen_map.csv`

공공 데이터의 알레르겐 표기(19종) → 우리 키(16종) 변환표.
공공 데이터 import 시 이 표를 적용합니다.
