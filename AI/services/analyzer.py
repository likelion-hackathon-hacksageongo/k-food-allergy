"""
식당 알레르겐 분석 서비스

사용자의 알레르기 프로필과 식당 전체 메뉴를 OpenAI API로 분석하여
메뉴별 적합도 + 식당 전체 점수를 반환합니다.
"""

import json
import time
from openai import OpenAI, RateLimitError, APIError

from config import (
    OPENAI_API_KEY,
    OPENAI_MODEL,
    PROMPTS_DIR,
    MAX_MENU_ITEMS_PER_REQUEST,
    TEMPERATURE_ANALYZER,
)
from schemas.types import (
    UserAllergyProfile,
    RestaurantInput,
    RestaurantAnalysisResult,
    LANGUAGE_NAMES,
)


# 시스템 프롬프트 로드
_SYSTEM_PROMPT = (PROMPTS_DIR / "analyzer_system.txt").read_text(encoding="utf-8")

# OpenAI 응답 JSON 스키마 (Structured Outputs)
_RESPONSE_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "restaurant_analysis",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "restaurant_id": {"type": "integer"},
                "restaurant_name": {"type": "string"},
                "overall_score": {"type": "integer"},
                "overall_suitability": {
                    "type": "string",
                    "enum": ["safe", "caution", "avoid", "unknown"],
                },
                "safe_menu_count": {"type": "integer"},
                "caution_menu_count": {"type": "integer"},
                "avoid_menu_count": {"type": "integer"},
                "risk_summary": {"type": "string"},
                "cross_contamination_notes": {"type": "string"},
                "menu_results": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "menu_id": {"type": "integer"},
                            "menu_name": {"type": "string"},
                            "suitability": {
                                "type": "string",
                                "enum": ["safe", "caution", "avoid", "unknown"],
                            },
                            "info_level": {
                                "type": "string",
                                "enum": ["confirmed", "pattern", "insufficient"],
                            },
                            "allergen_details": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "allergen": {"type": "string"},
                                        "likelihood": {
                                            "type": "string",
                                            "enum": ["confirmed", "likely", "possible", "none"],
                                        },
                                        "source": {"type": "string"},
                                        "hidden_risk": {"type": "string"},
                                    },
                                    "required": ["allergen", "likelihood", "source", "hidden_risk"],
                                    "additionalProperties": False,
                                },
                            },
                            "check_items": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "summary": {"type": "string"},
                        },
                        "required": [
                            "menu_id", "menu_name", "suitability", "info_level",
                            "allergen_details", "check_items", "summary",
                        ],
                        "additionalProperties": False,
                    },
                },
            },
            "required": [
                "restaurant_id", "restaurant_name", "overall_score",
                "overall_suitability", "safe_menu_count", "caution_menu_count",
                "avoid_menu_count", "risk_summary", "cross_contamination_notes",
                "menu_results",
            ],
            "additionalProperties": False,
        },
    },
}


def _build_user_message(
    profile: UserAllergyProfile,
    restaurant: RestaurantInput,
    language: str = "ko",
) -> str:
    """사용자 메시지 구성"""
    allergen_list = ", ".join(a.value for a in profile.allergens)

    menu_lines = []
    for item in restaurant.menu_items:
        ingredients_str = ", ".join(item.ingredients) if item.ingredients else "정보 없음"
        menu_lines.append(
            f"  - ID: {item.id} | {item.name}"
            f"{(' | ' + item.description) if item.description else ''}"
            f" | 재료: {ingredients_str}"
        )

    menus_text = "\n".join(menu_lines)

    # 언어 지시
    if language == "ko":
        lang_instruction = ""
    else:
        lang_name = LANGUAGE_NAMES.get(language, "English")
        lang_instruction = (
            f"\n\n## 출력 언어\n"
            f"모든 텍스트 필드(summary, risk_summary, cross_contamination_notes, "
            f"source, hidden_risk, check_items)를 {lang_name}로 작성하세요. "
            f"메뉴명(menu_name)은 원래 한국어 이름을 유지하되, 괄호 안에 {lang_name} 번역을 추가하세요. "
            f"예: \"된장찌개 (Soybean Paste Stew)\""
        )

    return (
        f"## 사용자 알레르기 프로필\n"
        f"알레르겐: {allergen_list}\n\n"
        f"## 식당 정보\n"
        f"ID: {restaurant.id}\n"
        f"식당명: {restaurant.name}\n"
        f"카테고리: {restaurant.category}\n\n"
        f"## 메뉴 목록 (총 {len(restaurant.menu_items)}개)\n"
        f"{menus_text}\n\n"
        f"위 정보를 바탕으로 각 메뉴별 알레르겐 분석과 식당 전체 적합도 점수를 산출하세요."
        f"{lang_instruction}"
    )


def analyze_restaurant(
    profile: UserAllergyProfile,
    restaurant: RestaurantInput,
    language: str = "ko",
) -> RestaurantAnalysisResult:
    """
    식당 전체 메뉴를 사용자 알레르기 프로필 기준으로 분석합니다.

    Args:
        profile: 사용자 알레르기 프로필
        restaurant: 식당 정보 (메뉴 포함)
        language: 응답 언어 코드 (ko, en, ja, zh, vi, th, es, fr)

    Returns:
        RestaurantAnalysisResult: 식당 전체 분석 결과

    Raises:
        ValueError: 메뉴가 너무 많은 경우 (MAX_MENU_ITEMS_PER_REQUEST 초과)
        openai.APIError: OpenAI API 호출 실패 시
    """
    from cache import analysis_cache

    if len(restaurant.menu_items) > MAX_MENU_ITEMS_PER_REQUEST:
        raise ValueError(
            f"메뉴 수가 {MAX_MENU_ITEMS_PER_REQUEST}개를 초과합니다. "
            f"({len(restaurant.menu_items)}개) 분할 요청이 필요합니다."
        )

    # 캐시 확인 (언어별 캐시 분리)
    cache_data = {
        "allergens": sorted(a.value for a in profile.allergens),
        "restaurant_id": restaurant.id,
        "menu_ids": sorted(m.id for m in restaurant.menu_items),
        "language": language,
    }
    cached = analysis_cache.get("analyze", cache_data)
    if cached:
        return RestaurantAnalysisResult(**cached)

    client = OpenAI(api_key=OPENAI_API_KEY)

    user_message = _build_user_message(profile, restaurant, language)

    # Rate limit 대응: 최대 3회 재시도 (exponential backoff)
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=OPENAI_MODEL,
                temperature=TEMPERATURE_ANALYZER,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                response_format=_RESPONSE_SCHEMA,
            )
            break
        except RateLimitError:
            if attempt < max_retries - 1:
                wait_time = (2 ** attempt) * 5  # 5s, 10s, 20s
                time.sleep(wait_time)
            else:
                raise

    raw_json = response.choices[0].message.content
    data = json.loads(raw_json)

    # 결과 캐시 저장
    analysis_cache.set("analyze", cache_data, data)

    return RestaurantAnalysisResult(**data)
