"""
Thin client for the AI team's live analysis server (see AI/INTEGRATION_GUIDE.md).

Runs separately on AI_SERVICE_URL (default http://localhost:8100, their
`uvicorn main:app --port 8100`). We call it synchronously per-request and
relay its response - no caching/precompute wired up yet (see the "later"
note in ai_integration/views.py).
"""

import requests
from django.conf import settings


class AIServiceError(Exception):
    """Raised on network failure, timeout, or a non-200 from the AI service."""
    pass


def _post(path: str, payload: dict) -> dict:
    url = f"{settings.AI_SERVICE_URL.rstrip('/')}{path}"
    try:
        response = requests.post(url, json=payload, timeout=20)
    except requests.RequestException as e:
        raise AIServiceError(f"AI 서버({url})에 연결할 수 없습니다: {e}")

    if response.status_code != 200:
        raise AIServiceError(f"AI 서버 오류 ({response.status_code}): {response.text[:500]}")

    return response.json()


def analyze_restaurant(allergens: list[str], restaurant: dict, language: str = 'en') -> dict:
    """POST /analyze - menu-by-menu suitability + restaurant overall_score."""
    return _post('/analyze', {
        'allergens': allergens,
        'restaurant': restaurant,
        'language': language,
    })


def generate_query(
    allergens: list[str],
    restaurant_name: str,
    menu_name: str | None,
    situations: list[str],
    language: str = 'en',
) -> dict:
    """POST /query - on-site inquiry phrases (Step 5 of the plan doc)."""
    payload = {
        'allergens': allergens,
        'restaurant_name': restaurant_name,
        'situations': situations,
        'language': language,
    }
    if menu_name:
        payload['menu_name'] = menu_name
    return _post('/query', payload)
