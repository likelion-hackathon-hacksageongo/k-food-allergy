# AI 분석 결과 → 백엔드 전달 포맷

AI팀이 배치로 분석한 식당/메뉴 알레르겐 정보를 백엔드 DB에 반영하기 위한 파일 포맷과 절차입니다.

## 파일 포맷

JSON 파일 하나에 메뉴 아이템별 분석 결과를 리스트로 담아서 전달합니다.

```json
[
  {
    "restaurant_name_ko": "홍대 순두부집",
    "menu_item_name_ko": "해물 순두부찌개",
    "info_level": "confirmed",
    "allergens": [
      {
        "allergen_key": "shellfish",
        "likelihood": "confirmed",
        "source": "ai_inference",
        "notes": "새우, 조개 포함 확인됨"
      },
      {
        "allergen_key": "egg",
        "likelihood": "likely",
        "source": "cooking_pattern",
        "notes": "완성 시 날계란 추가되는 경우 많음"
      }
    ]
  }
]
```

## 필드 설명

| 필드 | 값 | 설명 |
|---|---|---|
| `restaurant_name_ko` | 문자열 | DB에 이미 있는 식당의 **한글 이름**과 정확히 일치해야 함 (영문 name 아님) |
| `menu_item_name_ko` | 문자열 | 그 식당 메뉴의 **한글 이름**과 정확히 일치해야 함 |
| `info_level` | `confirmed` / `pattern` / `insufficient` | 이 메뉴 정보가 얼마나 확실한지 (공식확인 / 일반 조리 패턴 / 정보 부족) |
| `allergens` | 리스트 | 이 메뉴에서 검출된 알레르겐들. 없으면 빈 리스트 `[]` |
| `allergens[].allergen_key` | 아래 16개 중 하나 | 알레르겐 종류 |
| `allergens[].likelihood` | `confirmed` / `likely` / `possible` / `none` | 이 알레르겐이 들어있을 가능성 |
| `allergens[].source` | 문자열 (자유값) | 예: `ai_inference`, `cooking_pattern` |
| `allergens[].notes` | 문자열 (선택) | 추가 설명 |

### `likelihood` 4단계 정의

| 값 | 의미 |
|---|---|
| `confirmed` | 들어감이 확실함 |
| `likely` | 들어갔을 수 있으니 확인 필요 |
| `possible` | 알 수 없음 |
| `none` | 들어가지 않을 확률이 높음 |

매칭 시 `confirmed`만 위험(danger)으로 처리되고, `likely`/`possible`은 경고(warning)로 처리됩니다. `none`은 위험도 계산에서 제외됩니다(정보가 없는 것과 다르게, 명시적으로 "낮은 확률"이라는 판단 결과이므로).

## `allergen_key` 허용값 (16종, 철자 그대로 사용)

```
shellfish, nuts, wheat, soy, egg, dairy, fish, mollusk,
peach, peanut, pork, beef, chicken, sulfites, buckwheat, tomato
```

## 주의사항

- `restaurant_name_ko` / `menu_item_name_ko`는 DB에 이미 존재해야 매칭됩니다 (Data팀이 먼저 식당/메뉴를 등록해둔 상태여야 함). 없으면 해당 항목은 건너뛰고 결과에 로그로 표시됩니다.
- 여러 번 실행해도 안전합니다 (같은 메뉴+알레르겐 조합이면 기존 값을 덮어쓰고, 중복 행이 생기지 않습니다).

## 백엔드에서 반영하는 방법

```bash
# 1. 먼저 dry-run으로 검증 (DB에 실제로 쓰지 않음)
python manage.py import_allergen_analysis analysis.json --dry-run

# 2. 문제 없으면 실제 반영
python manage.py import_allergen_analysis analysis.json
```

커맨드 구현: [`backend/menus/management/commands/import_allergen_analysis.py`](../menus/management/commands/import_allergen_analysis.py)
