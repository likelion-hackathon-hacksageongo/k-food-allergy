"""
Thin client for Kakao Local API (keyword-based place search).

Docs: https://developers.kakao.com/docs/latest/ko/local/dev-guide#search-by-keyword
Needs `KAKAO_REST_API_KEY` in settings/.env (developers.kakao.com -> 앱 만들기 -> REST API 키).

Note: this API does NOT return business hours - only place_name, category,
phone, road address, coordinates, and a kakao map place URL/id.
"""

import requests
from django.conf import settings

KEYWORD_SEARCH_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"


class KakaoAPIError(Exception):
    pass


def search_place(query: str, longitude: float | None = None, latitude: float | None = None) -> dict | None:
    """
    Search Kakao Local by keyword (e.g. restaurant name + neighborhood) and
    return the best-matching place, or None if nothing was found.

    If `longitude`/`latitude` are given, results are biased toward that point
    (`x`/`y` in Kakao's API), which helps disambiguate common restaurant names.

    Returns a dict: {place_name, category_name, phone, road_address_name,
    address_name, longitude, latitude, place_url, id} or None.
    """
    if not settings.KAKAO_REST_API_KEY:
        raise KakaoAPIError(
            "KAKAO_REST_API_KEY is not set. Get one at https://developers.kakao.com/ "
            "(앱 만들기 -> REST API 키) and add it to backend/.env"
        )

    headers = {"Authorization": f"KakaoAK {settings.KAKAO_REST_API_KEY}"}
    params = {"query": query, "size": 5}
    if longitude is not None and latitude is not None:
        params.update({"x": longitude, "y": latitude, "radius": 2000, "sort": "distance"})

    response = requests.get(KEYWORD_SEARCH_URL, headers=headers, params=params, timeout=5)
    if response.status_code != 200:
        raise KakaoAPIError(f"Kakao API returned {response.status_code}: {response.text}")

    documents = response.json().get("documents", [])
    if not documents:
        return None

    best = documents[0]
    return {
        "place_name": best.get("place_name", ""),
        "category_name": best.get("category_name", ""),
        "phone": best.get("phone", ""),
        "road_address_name": best.get("road_address_name", ""),
        "address_name": best.get("address_name", ""),
        "longitude": float(best["x"]),
        "latitude": float(best["y"]),
        "place_url": best.get("place_url", ""),
        "id": best.get("id", ""),
    }
