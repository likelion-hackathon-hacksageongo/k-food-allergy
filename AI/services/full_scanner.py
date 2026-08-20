"""
메뉴판 스캔 + 문의 문장 통합 서비스

한 번의 API 호출로:
1. 메뉴판 인식 + 번역
2. 알레르겐 매칭
3. 위험 메뉴에 대한 한국어 문의 문장 생성

모두 처리합니다.
"""

import base64
import json
import time
from openai import OpenAI, RateLimitError

from config import (
    OPENAI_API_KEY,
    OPENAI_MODEL,
    PROMPTS_DIR,
)
from schemas.types import (
    FullScanResult,
    LANGUAGE_NAMES,
)


# 시스템 프롬프트 (경량)
_SYSTEM_PROMPT = """한국어 메뉴판 이미지 분석 + 현장 문의 문장 생성 전문가.

# 역할
메뉴판 사진을 받아:
1. 메뉴 인식 + 사용자 언어 번역
2. 사용자 알레르겐 매칭 + safety_level 판정
3. danger/caution 메뉴에 대해 직원에게 보여줄 한국어 문의 문장 생성

# 인식/번역 규칙
- 모든 음식 메뉴 추출 (카테고리 제목 제외)
- 의미 번역: 된장찌개 → Soybean Paste Stew
- 고유명사: 비빔밥 → Bibimbap (Mixed Rice Bowl)

# 알레르겐 판정 — 안전 우선 원칙
불확실하면 반드시 caution 이상으로 판정. "safe"는 확실히 포함되지 않는 경우에만.

## 한식 숨은 재료 (반드시 고려)
- 모든 찌개/국: 멸치육수(fish) 또는 조개육수(shellfish) 사용 가능
- 순두부찌개: 달걀 토핑(egg), 해산물(shellfish), 멸치육수(fish), 대두(soy) 포함 가능
- 김치찌개/부대찌개: 돼지고기(pork), 새우젓(shellfish), 멸치액젓(fish)
- 된장찌개: 대두(soy), 멸치육수(fish), 조개(shellfish)
- 김밥/비빔밥: 달걀(egg), 참기름, 간장(soy), 게맛살(wheat+fish)
- 전/부침개: 밀가루(wheat), 달걀(egg)
- 불고기/갈비: 간장(soy), 배, 설탕
- 떡볶이: 고추장(soy+wheat), 어묵(wheat+fish)
- 삼겹살/목살: 쌈장(soy), 된장(soy)
- 냉면: 메밀(buckwheat), 달걀(egg), 소고기(beef)
- 삼계탕: 닭(chicken), 찹쌀, 잣(nuts)
- 국밥류: 돼지(pork) 또는 소(beef) 사골 육수

## 판정 기준
- danger: 사용자 알레르겐이 주재료로 확실 포함
- caution: 포함 가능성 있음 (육수, 양념, 토핑 등)
- safe: 사용자 알레르겐과 관련된 재료가 전혀 없을 가능성이 높음
- unknown: 메뉴명만으로 판단 불가

## 무시할 항목
- 원산지 정보 (예: "원산지 - 김치: 국내산, 돼지고기: 국내산") → 메뉴가 아님, description에도 포함하지 않음
- 가격 정보 → 무시

# 문의 문장 (staff_query)
- danger/caution 메뉴에만 생성 (safe/unknown은 빈 문자열)
- 정중한 존댓말, 40자 이내, 구체적
- 형식: "이 [메뉴]에 [알레르겐 한국어]이/가 들어가나요?"
- query_explanation: 사용자 언어로 문장 의미 설명

# intro_text
"저는 [알레르겐 한국어 목록]에 심한 알레르기가 있습니다. 확인 부탁드립니다."
알레르겐 없으면 빈 문자열.

# 출력
JSON 스키마에 맞춰 응답."""

# 알레르겐 한국어 매핑 (프롬프트 보조)
_ALLERGEN_KO = {
    "shellfish": "갑각류(새우,게)", "nuts": "견과류(호두,잣)", "wheat": "밀(밀가루)",
    "soy": "대두(콩,된장,간장)", "egg": "달걀", "dairy": "유제품(우유,치즈)",
    "fish": "생선(멸치,고등어)", "mollusk": "조개류(오징어,전복)", "peach": "복숭아",
    "peanut": "땅콩", "pork": "돼지고기", "beef": "쇠고기", "chicken": "닭고기",
    "sulfites": "아황산류", "buckwheat": "메밀", "tomato": "토마토",
}

# 응답 JSON 스키마
_RESPONSE_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "full_scan",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "restaurant_name": {"type": "string"},
                "intro_text": {"type": "string"},
                "menu_items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "original_text": {"type": "string"},
                            "translated_name": {"type": "string"},
                            "description": {"type": "string"},
                            "allergen_warnings": {"type": "array", "items": {"type": "string"}},
                            "allergen_keys": {"type": "array", "items": {"type": "string"}},
                            "safety_level": {"type": "string", "enum": ["safe", "caution", "danger", "unknown"]},
                            "staff_query": {"type": "string"},
                            "query_explanation": {"type": "string"},
                        },
                        "required": [
                            "original_text", "translated_name", "description",
                            "allergen_warnings", "allergen_keys", "safety_level",
                            "staff_query", "query_explanation",
                        ],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["restaurant_name", "intro_text", "menu_items"],
            "additionalProperties": False,
        },
    },
}


def full_scan_menu(
    image_bytes: bytes,
    allergens: list[str],
    language: str = "en",
    image_format: str = "jpeg",
) -> FullScanResult:
    """
    메뉴판 스캔 + 번역 + 알레르겐 체크 + 문의 문장 생성을 한 번에 수행.

    Args:
        image_bytes: 메뉴판 이미지
        allergens: 사용자 알레르겐 코드 목록
        language: 번역/설명 대상 언어
        image_format: 이미지 형식

    Returns:
        FullScanResult: 메뉴 + 번역 + 알레르겐 + 문의 문장 통합 결과
    """
    client = OpenAI(api_key=OPENAI_API_KEY)

    base64_image = base64.b64encode(image_bytes).decode("utf-8")
    lang_name = LANGUAGE_NAMES.get(language, "English")
    allergen_ko_list = ", ".join(_ALLERGEN_KO.get(a, a) for a in allergens) if allergens else "없음"
    allergen_en_list = ", ".join(allergens) if allergens else "none"

    user_message = (
        f"알레르겐: {allergen_en_list} (한국어: {allergen_ko_list})\n"
        f"번역 언어: {lang_name}\n\n"
        f"이 메뉴판을 분석하세요. danger/caution 메뉴에는 staff_query(한국어 문의 문장)를 생성하세요.\n"
        f"중요: allergen_keys에는 반드시 영어 코드만 사용 (shellfish, soy, wheat, egg 등). 한국어 재료명 X."
    )

    # Rate limit 대응
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=OPENAI_MODEL,
                temperature=0,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": user_message},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/{image_format};base64,{base64_image}",
                                    "detail": "high",
                                },
                            },
                        ],
                    },
                ],
                response_format=_RESPONSE_SCHEMA,
            )
            break
        except RateLimitError:
            if attempt < max_retries - 1:
                time.sleep((2 ** attempt) * 5)
            else:
                raise

    raw_json = response.choices[0].message.content
    data = json.loads(raw_json)

    # 통계 계산
    menu_items = data["menu_items"]
    danger_count = sum(1 for m in menu_items if m["safety_level"] == "danger")
    caution_count = sum(1 for m in menu_items if m["safety_level"] == "caution")
    safe_count = sum(1 for m in menu_items if m["safety_level"] == "safe")

    return FullScanResult(
        menu_items=menu_items,
        restaurant_name=data.get("restaurant_name", ""),
        total_items=len(menu_items),
        danger_count=danger_count,
        caution_count=caution_count,
        safe_count=safe_count,
        intro_text=data.get("intro_text", ""),
        scan_language="ko",
        user_language=language,
    )
