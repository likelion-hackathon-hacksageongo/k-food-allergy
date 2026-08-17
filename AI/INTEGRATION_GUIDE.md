# AI 모듈 연동 가이드

BE 담당자를 위한 AI 모듈 연동 방법 안내입니다.

---

## 1. AI 서버 실행 방법

```bash
cd AI
source .venv/Scripts/activate   # Windows Git Bash
pip install -r requirements.txt
uvicorn main:app --reload --port 8100
```

- Swagger 문서: http://localhost:8100/docs
- Health check: `GET http://localhost:8100/health`

---

## 2. API 엔드포인트

### POST /analyze — 식당 분석

사용자 알레르겐 + 식당 전체 메뉴를 보내면, 메뉴별 적합도와 식당 전체 점수를 반환합니다.

**요청:**
```json
{
  "allergens": ["soy", "shellfish", "wheat"],
  "restaurant": {
    "id": 1,
    "name": "홍대 한솥밥",
    "category": "한식",
    "menu_items": [
      {
        "id": 101,
        "name": "된장찌개",
        "description": "된장, 두부, 호박",
        "ingredients": ["된장", "두부", "호박"]
      },
      {
        "id": 102,
        "name": "삼겹살 구이",
        "description": "삼겹살, 쌈채소",
        "ingredients": ["삼겹살", "상추", "마늘"]
      }
    ]
  }
}
```

**응답:**
```json
{
  "restaurant_id": 1,
  "restaurant_name": "홍대 한솥밥",
  "overall_score": 65,
  "overall_suitability": "caution",
  "safe_menu_count": 1,
  "caution_menu_count": 1,
  "avoid_menu_count": 0,
  "risk_summary": "대두 기반 양념(된장, 간장) 다수 사용. 밀·갑각류는 일부 메뉴에서 확인 필요.",
  "cross_contamination_notes": "같은 주방에서 해물 요리를 조리할 경우 교차오염 가능.",
  "menu_results": [
    {
      "menu_id": 101,
      "menu_name": "된장찌개",
      "suitability": "avoid",
      "info_level": "sufficient",
      "allergen_details": [
        {
          "allergen": "soy",
          "likelihood": "confirmed",
          "source": "된장, 두부는 대두 유래",
          "hidden_risk": ""
        }
      ],
      "check_items": ["육수 재료 확인", "간장 사용 여부"],
      "summary": "대두(된장, 두부)가 주재료로 포함되어 회피 권장."
    }
  ]
}
```

---

### POST /query — 현장 문의 문장 생성

사용자 알레르겐 + 상황을 보내면, 직원에게 보여줄 한국어 문장을 생성합니다.

**요청:**
```json
{
  "allergens": ["peanut", "shellfish", "wheat"],
  "restaurant_name": "홍대 한솥밥",
  "menu_name": "된장찌개",
  "situations": ["ingredient_check", "broth_sauce", "cross_contamination"]
}
```

**상황 코드:**
| 코드 | 설명 |
|------|------|
| `ingredient_check` | 특정 메뉴 재료 확인 |
| `broth_sauce` | 육수·소스 원재료 확인 |
| `cross_contamination` | 교차오염 (조리 도구 공유) 확인 |
| `modification` | 재료 변경/제거 가능 여부 |

**응답:**
```json
{
  "intro_text": "저는 땅콩, 갑각류(새우, 게), 밀에 알레르기가 있습니다.",
  "queries": [
    {
      "situation": "ingredient_check",
      "situation_label": "재료 확인",
      "korean_text": "이 된장찌개에 땅콩이나 새우가 들어가나요? 밀가루가 포함된 재료가 있는지도 확인해 주세요.",
      "english_note": "Asking if this doenjang-jjigae contains peanuts, shrimp, or wheat-based ingredients."
    }
  ],
  "disclaimer": "이 문장은 직원과의 의사소통을 돕기 위한 참고 자료입니다. 실제 조리 환경을 보증하지 않습니다."
}
```

---

## 3. 지원 알레르겐 코드 (16종)

| 코드 | 한국어 | 예시 |
|------|--------|------|
| `shellfish` | 갑각류 | 새우, 게, 랍스터 |
| `nuts` | 견과류 | 호두, 아몬드, 잣 |
| `wheat` | 밀·글루텐 | 밀가루, 보리, 호밀 |
| `soy` | 대두 | 두부, 된장, 간장 |
| `egg` | 달걀 | 계란 |
| `dairy` | 유제품 | 우유, 치즈, 버터 |
| `fish` | 생선·어류 | 멸치, 고등어 |
| `mollusk` | 조개류 | 전복, 오징어, 조개 |
| `peach` | 복숭아 | |
| `peanut` | 땅콩 | |
| `pork` | 돼지고기 | |
| `beef` | 쇠고기 | |
| `chicken` | 닭고기 | |
| `sulfites` | 아황산류 | 와인, 식초 |
| `buckwheat` | 메밀 | |
| `tomato` | 토마토 | |

---

## 4. Django 연동 방법 (BE가 준비되면)

Django에서 이 AI 서버를 호출하는 방식은 두 가지:

### 방법 A: HTTP 호출 (권장 — 독립 배포 가능)

```python
import requests

def analyze_restaurant(user_allergens, restaurant_data):
    response = requests.post(
        "http://localhost:8100/analyze",
        json={
            "allergens": user_allergens,
            "restaurant": restaurant_data,
        }
    )
    return response.json()
```

### 방법 B: 직접 import (같은 서버에서 실행 시)

```python
import sys
sys.path.insert(0, "/path/to/AI")

from services.analyzer import analyze_restaurant
from schemas.types import UserAllergyProfile, RestaurantInput
```

---

## 5. 주의사항

- `.env` 파일에 `OPENAI_API_KEY` 필수 (`.env.example` 참고)
- 기본 모델: `gpt-4o-mini` (비용 효율적, 변경 가능)
- AI 서버 포트: `8100` (Django 8000, Vite 5173과 충돌 없음)
- 응답 시간: 분석 약 3~8초, 문장 생성 약 2~5초 (첫 호출 기준)


---

## 6. 사전 분석 (Pre-compute) 엔드포인트

지도 뷰가 즉시 로딩되려면, 식당 점수를 미리 계산해 저장해야 합니다.

### 흐름

```
사용자 프로필 등록/변경
    → BE가 POST /precompute/trigger 호출 (즉시 반환)
    → AI가 백그라운드에서 모든 식당 분석
    → 결과 저장

사용자가 지도 열기
    → FE가 GET /scores/{user_id} 호출
    → 즉시 반환 (<50ms)
```

### POST /precompute/trigger — 전체 식당 사전 분석

BE가 호출하는 시점: 사용자 프로필 등록/변경 시

```json
{
  "user_id": "user_123",
  "allergens": ["soy", "shellfish", "wheat"],
  "restaurants": [ /* restaurants.json 형식 */ ],
  "language": "en"
}
```

응답 (즉시 반환):
```json
{
  "status": "started",
  "user_id": "user_123",
  "restaurant_count": 12,
  "message": "백그라운드에서 분석이 진행됩니다."
}
```

### POST /precompute/restaurant — 단일 식당 재분석

BE가 호출하는 시점: 식당 메뉴가 변경되었을 때

```json
{
  "user_id": "user_123",
  "allergens": ["soy", "shellfish", "wheat"],
  "restaurant": { /* 단일 식당 데이터 */ },
  "language": "en"
}
```

### GET /scores/{user_id} — 지도 뷰 즉시 조회

```json
{
  "user_id": "user_123",
  "computed_at": "2026-08-15T14:30:00",
  "restaurants": {
    "1": {
      "restaurant_id": 1,
      "restaurant_name": "홍대 한솥밥",
      "overall_score": 72,
      "overall_suitability": "caution",
      "safe_menu_count": 2,
      "caution_menu_count": 2,
      "avoid_menu_count": 1,
      "risk_summary": "Soy-based seasonings widely used..."
    }
  }
}
```

---

## 7. 언어 파라미터 (`language`)

모든 분석 엔드포인트에 `language` 필드를 추가할 수 있습니다:

| 코드 | 언어 |
|------|------|
| `ko` | 한국어 (기본값) |
| `en` | English |
| `ja` | 日本語 |
| `zh` | 中文 |
| `vi` | Tiếng Việt |
| `th` | ภาษาไทย |
| `es` | Español |
| `fr` | Français |

규칙:
- `/analyze`, `/analyze/batch`, `/precompute/*`: 결과 텍스트가 해당 언어로 출력
- `/query`: `korean_text`는 항상 한국어 (직원에게 보여줄 용도), `english_note`와 `situation_label`은 사용자 언어
