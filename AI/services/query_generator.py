"""
현장 문의 문장 생성 서비스

사용자의 알레르기 정보와 문의 상황을 기반으로
식당 직원에게 보여줄 한국어 문장을 생성합니다.
"""

import json
from openai import OpenAI

from config import (
    OPENAI_API_KEY,
    OPENAI_MODEL,
    PROMPTS_DIR,
    TEMPERATURE_QUERY_GEN,
)
from schemas.types import (
    QueryContext,
    QueryGeneratorResult,
    LANGUAGE_NAMES,
)


# 시스템 프롬프트 로드
_SYSTEM_PROMPT = (PROMPTS_DIR / "query_generator_system.txt").read_text(encoding="utf-8")

# OpenAI 응답 JSON 스키마 (Structured Outputs)
_RESPONSE_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "query_generation",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "intro_text": {"type": "string"},
                "queries": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "situation": {"type": "string"},
                            "situation_label": {"type": "string"},
                            "korean_text": {"type": "string"},
                            "english_note": {"type": "string"},
                        },
                        "required": ["situation", "situation_label", "korean_text", "english_note"],
                        "additionalProperties": False,
                    },
                },
                "disclaimer": {"type": "string"},
            },
            "required": ["intro_text", "queries", "disclaimer"],
            "additionalProperties": False,
        },
    },
}

# 상황 코드 → 한국어 설명 매핑 (프롬프트 보조용)
_SITUATION_DESCRIPTIONS = {
    "ingredient_check": "특정 메뉴에 알레르겐 재료가 포함되어 있는지 확인",
    "broth_sauce": "육수, 양념장, 소스의 원재료 확인",
    "cross_contamination": "조리 도구·기름·조리 공간 공유 여부 확인",
    "modification": "특정 재료를 빼거나 대체할 수 있는지 요청",
}


def _build_user_message(context: QueryContext, language: str = "ko") -> str:
    """사용자 메시지 구성"""
    allergen_list = ", ".join(a.value for a in context.allergens)

    situation_lines = []
    for sit in context.situations:
        desc = _SITUATION_DESCRIPTIONS.get(sit, sit)
        situation_lines.append(f"  - {sit}: {desc}")
    situations_text = "\n".join(situation_lines)

    parts = [
        f"## 사용자 알레르기 정보",
        f"알레르겐: {allergen_list}",
        f"",
        f"## 문의 상황",
        situations_text,
    ]

    if context.restaurant_name:
        parts.append(f"\n## 식당 정보")
        parts.append(f"식당명: {context.restaurant_name}")

    if context.menu_name:
        parts.append(f"메뉴명: {context.menu_name}")

    parts.append(
        f"\n위 정보를 바탕으로 각 상황에 맞는 한국어 문의 문장을 생성하세요."
    )

    # 언어 지시: korean_text는 항상 한국어, 나머지 필드는 사용자 언어
    if language != "ko":
        lang_name = LANGUAGE_NAMES.get(language, "English")
        parts.append(
            f"\n## 출력 언어 안내\n"
            f"- korean_text: 반드시 한국어로 작성 (식당 직원에게 보여줄 문장)\n"
            f"- english_note: {lang_name}로 작성 (사용자가 문장의 의미를 이해할 수 있도록)\n"
            f"- situation_label: {lang_name}로 작성\n"
            f"- intro_text: 한국어로 작성 (직원에게 보여주는 소개 문장)\n"
            f"- disclaimer: {lang_name}로 작성"
        )

    return "\n".join(parts)


def generate_queries(context: QueryContext, language: str = "ko") -> QueryGeneratorResult:
    """
    사용자의 알레르기 정보와 상황에 맞는 한국어 문의 문장을 생성합니다.

    Args:
        context: 문의 문장 생성 요청 컨텍스트 (알레르겐, 상황, 식당/메뉴명)
        language: 사용자 인터페이스 언어 코드 (korean_text는 항상 한국어)

    Returns:
        QueryGeneratorResult: 생성된 문의 문장 목록

    Raises:
        openai.APIError: OpenAI API 호출 실패 시
    """
    from cache import query_cache

    # 캐시 확인 (언어별 분리)
    cache_data = {
        "allergens": sorted(a.value for a in context.allergens),
        "situations": sorted(context.situations),
        "restaurant_name": context.restaurant_name,
        "menu_name": context.menu_name,
        "language": language,
    }
    cached = query_cache.get("query", cache_data)
    if cached:
        return QueryGeneratorResult(**cached)

    client = OpenAI(api_key=OPENAI_API_KEY)

    user_message = _build_user_message(context, language)

    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        temperature=TEMPERATURE_QUERY_GEN,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        response_format=_RESPONSE_SCHEMA,
    )

    raw_json = response.choices[0].message.content
    data = json.loads(raw_json)

    # 결과 캐시 저장
    query_cache.set("query", cache_data, data)

    return QueryGeneratorResult(**data)
