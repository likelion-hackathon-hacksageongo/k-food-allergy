"""
사전 분석 서비스 (Pre-computation)

사용자 프로필이 등록/변경되거나 식당 메뉴가 변경될 때
백그라운드에서 모든 (사용자, 식당) 조합의 점수를 미리 계산합니다.

결과는 store.py를 통해 파일에 저장되며, 지도 뷰에서 즉시 읽어옵니다.
"""

import concurrent.futures
import time
from typing import Callable

from schemas.types import (
    UserAllergyProfile,
    AllergenKey,
    RestaurantInput,
    MenuItemInput,
)
from services.analyzer import analyze_restaurant
from store import (
    save_user_scores,
    delete_user_scores,
    update_restaurant_score,
    list_all_users,
    get_user_scores,
)


def precompute_for_user(
    user_id: str,
    allergens: list[str],
    restaurants: list[dict],
    language: str = "ko",
    max_workers: int = 5,
    on_progress: Callable[[int, int], None] | None = None,
) -> dict:
    """
    특정 사용자에 대해 모든 식당의 적합도를 사전 분석합니다.

    Args:
        user_id: 사용자 식별자
        allergens: 알레르겐 코드 목록 (예: ["soy", "shellfish"])
        restaurants: 식당 목록 (RestaurantInput 형식의 dict)
        language: 응답 언어
        max_workers: 병렬 처리 수 (OpenAI rate limit 고려)
        on_progress: 진행 콜백 (완료 수, 전체 수)

    Returns:
        {"total": N, "success": N, "failed": N, "elapsed": seconds}
    """
    profile = UserAllergyProfile(
        allergens=[AllergenKey(a) for a in allergens]
    )

    # 기존 결과 삭제 (재계산)
    delete_user_scores(user_id)

    results = {}
    success_count = 0
    failed_count = 0
    total = len(restaurants)
    start_time = time.time()

    def _analyze_one(restaurant_dict: dict) -> tuple[str, dict | None]:
        """단일 식당 분석 → (restaurant_id, summary or None)"""
        try:
            restaurant = RestaurantInput(**restaurant_dict)

            if not restaurant.menu_items:
                return str(restaurant.id), None

            result = analyze_restaurant(profile, restaurant, language=language)

            summary = {
                "restaurant_id": result.restaurant_id,
                "restaurant_name": result.restaurant_name,
                "overall_score": result.overall_score,
                "overall_suitability": result.overall_suitability.value,
                "safe_menu_count": result.safe_menu_count,
                "caution_menu_count": result.caution_menu_count,
                "avoid_menu_count": result.avoid_menu_count,
                "risk_summary": result.risk_summary,
            }
            return str(restaurant.id), summary

        except Exception as e:
            rid = restaurant_dict.get("id", "unknown")
            return str(rid), None

    # 병렬 분석
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_analyze_one, r): r for r in restaurants
        }

        for future in concurrent.futures.as_completed(futures):
            rid, summary = future.result()
            if summary:
                results[rid] = summary
                success_count += 1
            else:
                failed_count += 1

            if on_progress:
                on_progress(success_count + failed_count, total)

    # 결과 저장
    save_user_scores(user_id, allergens, language, results)

    elapsed = time.time() - start_time

    return {
        "total": total,
        "success": success_count,
        "failed": failed_count,
        "elapsed": round(elapsed, 2),
    }


def precompute_single_restaurant(
    user_id: str,
    allergens: list[str],
    restaurant: dict,
    language: str = "ko",
) -> dict | None:
    """
    단일 식당만 재분석합니다 (메뉴 변경 시).
    전체 재계산 없이 한 식당의 결과만 갱신합니다.

    Returns:
        업데이트된 summary dict 또는 None
    """
    profile = UserAllergyProfile(
        allergens=[AllergenKey(a) for a in allergens]
    )

    try:
        restaurant_input = RestaurantInput(**restaurant)

        if not restaurant_input.menu_items:
            return None

        result = analyze_restaurant(profile, restaurant_input, language=language)

        summary = {
            "restaurant_id": result.restaurant_id,
            "restaurant_name": result.restaurant_name,
            "overall_score": result.overall_score,
            "overall_suitability": result.overall_suitability.value,
            "safe_menu_count": result.safe_menu_count,
            "caution_menu_count": result.caution_menu_count,
            "avoid_menu_count": result.avoid_menu_count,
            "risk_summary": result.risk_summary,
        }

        # 저장소 업데이트
        update_restaurant_score(user_id, str(restaurant_input.id), summary)

        return summary

    except Exception:
        return None


def precompute_restaurant_for_all_users(
    restaurant: dict,
    user_profiles: list[dict],
    max_workers: int = 3,
) -> dict:
    """
    식당 메뉴가 변경되었을 때, 모든 사용자에 대해 해당 식당만 재분석합니다.

    Args:
        restaurant: 변경된 식당 정보 (RestaurantInput 형식)
        user_profiles: [{"user_id": "...", "allergens": [...], "language": "..."}]
        max_workers: 병렬 처리 수

    Returns:
        {"total_users": N, "updated": N, "failed": N}
    """
    updated = 0
    failed = 0

    def _update_for_user(profile_dict: dict) -> bool:
        result = precompute_single_restaurant(
            user_id=profile_dict["user_id"],
            allergens=profile_dict["allergens"],
            restaurant=restaurant,
            language=profile_dict.get("language", "ko"),
        )
        return result is not None

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_update_for_user, p): p for p in user_profiles
        }

        for future in concurrent.futures.as_completed(futures):
            if future.result():
                updated += 1
            else:
                failed += 1

    return {
        "total_users": len(user_profiles),
        "updated": updated,
        "failed": failed,
    }
