"""
사전 분석 결과 영속 저장소

사용자별 식당 점수를 JSON 파일로 저장/조회합니다.
MVP 단계에서는 파일 기반, 이후 DB(PostgreSQL/Redis)로 교체 가능합니다.

저장 구조:
    data/scores/{user_id}.json
    {
        "user_id": "user_123",
        "allergens": ["soy", "shellfish"],
        "language": "en",
        "computed_at": "2026-08-15T14:30:00",
        "restaurants": {
            "1": { restaurant summary },
            "2": { restaurant summary },
            ...
        }
    }
"""

import json
import os
from pathlib import Path
from datetime import datetime
from typing import Any

# 저장 디렉토리
SCORES_DIR = Path(__file__).resolve().parent / "data" / "scores"
SCORES_DIR.mkdir(parents=True, exist_ok=True)


def _user_file(user_id: str) -> Path:
    """사용자별 파일 경로"""
    return SCORES_DIR / f"{user_id}.json"


def save_user_scores(
    user_id: str,
    allergens: list[str],
    language: str,
    restaurants: dict[str, dict],
):
    """
    사용자의 전체 식당 분석 결과를 저장합니다.

    Args:
        user_id: 사용자 식별자
        allergens: 사용자 알레르겐 목록
        language: 분석 언어
        restaurants: {restaurant_id: summary_dict} 형태
    """
    data = {
        "user_id": user_id,
        "allergens": sorted(allergens),
        "language": language,
        "computed_at": datetime.now().isoformat(),
        "restaurants": restaurants,
    }

    filepath = _user_file(user_id)
    filepath.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def get_user_scores(user_id: str) -> dict | None:
    """
    저장된 사용자 분석 결과를 조회합니다.

    Returns:
        저장된 데이터 dict 또는 None (미계산 시)
    """
    filepath = _user_file(user_id)
    if not filepath.exists():
        return None

    return json.loads(filepath.read_text(encoding="utf-8"))


def get_restaurant_score(user_id: str, restaurant_id: str) -> dict | None:
    """
    특정 사용자의 특정 식당 점수만 조회합니다.

    Returns:
        식당 요약 dict 또는 None
    """
    data = get_user_scores(user_id)
    if not data:
        return None

    return data["restaurants"].get(str(restaurant_id))


def update_restaurant_score(user_id: str, restaurant_id: str, summary: dict):
    """
    특정 식당의 점수만 업데이트합니다 (메뉴 변경 시).
    전체 재계산 없이 한 식당만 갱신할 때 사용.
    """
    data = get_user_scores(user_id)
    if not data:
        return

    data["restaurants"][str(restaurant_id)] = summary
    data["computed_at"] = datetime.now().isoformat()

    filepath = _user_file(user_id)
    filepath.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def delete_user_scores(user_id: str):
    """사용자 분석 결과 삭제 (프로필 변경 시 재계산 전)"""
    filepath = _user_file(user_id)
    if filepath.exists():
        filepath.unlink()


def list_all_users() -> list[str]:
    """저장된 모든 사용자 ID 목록"""
    return [f.stem for f in SCORES_DIR.glob("*.json")]


def is_stale(user_id: str, allergens: list[str]) -> bool:
    """
    저장된 결과가 현재 알레르겐 프로필과 다른지 확인합니다.
    다르면 재계산 필요.
    """
    data = get_user_scores(user_id)
    if not data:
        return True

    return sorted(allergens) != sorted(data.get("allergens", []))
