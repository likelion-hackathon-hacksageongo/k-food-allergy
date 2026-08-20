"""
메뉴판 스캔 서비스

메뉴판 사진을 OpenAI Vision API로 분석하여:
1. 메뉴 항목 인식
2. 사용자 언어로 번역
3. 알레르겐 매칭 및 경고 생성

한 번의 API 호출로 인식 + 번역 + 분석을 동시에 수행합니다.
"""

import base64
import json
import time
from pathlib import Path
from openai import OpenAI, RateLimitError

from config import (
    OPENAI_API_KEY,
    OPENAI_MODEL,
    PROMPTS_DIR,
)
from schemas.types import (
    MenuScanResult,
    LANGUAGE_NAMES,
)


# 시스템 프롬프트 로드
_SYSTEM_PROMPT = (PROMPTS_DIR / "menu_scan_system.txt").read_text(encoding="utf-8")

# OpenAI 응답 JSON 스키마
_RESPONSE_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "menu_scan",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "restaurant_name": {"type": "string"},
                "menu_items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "original_text": {"type": "string"},
                            "translated_name": {"type": "string"},
                            "description": {"type": "string"},
                            "price": {"type": "string"},
                            "allergen_warnings": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "allergen_keys": {
                                "type": "array",
                                "items": {"type": "string"},
                            },
                            "safety_level": {
                                "type": "string",
                                "enum": ["safe", "caution", "danger", "unknown"],
                            },
                        },
                        "required": [
                            "original_text", "translated_name", "description",
                            "price", "allergen_warnings", "allergen_keys", "safety_level",
                        ],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["restaurant_name", "menu_items"],
            "additionalProperties": False,
        },
    },
}


def _encode_image(image_bytes: bytes) -> str:
    """이미지를 base64로 인코딩"""
    return base64.b64encode(image_bytes).decode("utf-8")


def _build_user_message(
    allergens: list[str],
    language: str,
) -> str:
    """사용자 메시지 구성"""
    lang_name = LANGUAGE_NAMES.get(language, "English")
    allergen_list = ", ".join(allergens) if allergens else "없음 (모든 메뉴 안전)"

    return (
        f"## 사용자 정보\n"
        f"알레르겐: {allergen_list}\n"
        f"번역 언어: {lang_name}\n\n"
        f"## 요청\n"
        f"이 메뉴판 사진에서 모든 메뉴 항목을 인식하고:\n"
        f"1. 각 메뉴명을 {lang_name}로 번역\n"
        f"2. 주요 재료를 {lang_name}로 설명\n"
        f"3. 사용자 알레르겐({allergen_list})과 매칭하여 경고 생성\n"
        f"4. 각 메뉴의 safety_level 판정\n\n"
        f"allergen_warnings와 description은 {lang_name}로 작성하세요."
    )


def scan_menu(
    image_bytes: bytes,
    allergens: list[str],
    language: str = "en",
    image_format: str = "jpeg",
) -> MenuScanResult:
    """
    메뉴판 사진을 분석하여 번역 + 알레르겐 체크 결과를 반환합니다.

    Args:
        image_bytes: 메뉴판 이미지 바이트
        allergens: 사용자 알레르겐 코드 목록 (빈 리스트 = 알레르기 없음)
        language: 번역 대상 언어 코드
        image_format: 이미지 형식 (jpeg, png, webp, gif)

    Returns:
        MenuScanResult: 스캔된 메뉴 목록 + 번역 + 알레르겐 정보

    Raises:
        RateLimitError: API 한도 초과 시
    """
    client = OpenAI(api_key=OPENAI_API_KEY)

    base64_image = _encode_image(image_bytes)
    user_message = _build_user_message(allergens, language)

    # Rate limit 대응: 최대 3회 재시도
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=OPENAI_MODEL,
                temperature=0.3,
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
                wait_time = (2 ** attempt) * 5
                time.sleep(wait_time)
            else:
                raise

    raw_json = response.choices[0].message.content
    data = json.loads(raw_json)

    # MenuScanResult 구성
    return MenuScanResult(
        menu_items=data["menu_items"],
        restaurant_name=data.get("restaurant_name", ""),
        total_items=len(data["menu_items"]),
        scan_language="ko",
        user_language=language,
    )
