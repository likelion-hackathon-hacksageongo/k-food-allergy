"""
다국어 지원 테스트 스크립트

서버 실행 필요:
    uvicorn main:app --reload --port 8100

사용법:
    python test_multilang.py
"""

import requests
import time

BASE_URL = "http://localhost:8100"

# 테스트용 공통 데이터
ANALYZE_PAYLOAD_BASE = {
    "allergens": ["soy", "shellfish", "wheat"],
    "restaurant": {
        "id": 1,
        "name": "홍대 한솥밥",
        "category": "한식",
        "menu_items": [
            {"id": 101, "name": "된장찌개", "description": "된장, 두부, 호박", "ingredients": ["된장", "두부", "호박"]},
            {"id": 102, "name": "삼겹살 구이", "description": "삼겹살, 쌈채소", "ingredients": ["삼겹살", "상추"]},
            {"id": 103, "name": "해물파전", "description": "해물, 밀가루", "ingredients": ["밀가루", "새우", "오징어"]},
        ]
    }
}

QUERY_PAYLOAD_BASE = {
    "allergens": ["peanut", "shellfish"],
    "restaurant_name": "홍대 한솥밥",
    "menu_name": "된장찌개",
    "situations": ["ingredient_check", "broth_sauce"]
}


def print_section(title):
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


def test_analyze_language(lang: str, lang_label: str):
    """특정 언어로 분석 테스트"""
    payload = {**ANALYZE_PAYLOAD_BASE, "language": lang}

    start = time.time()
    res = requests.post(f"{BASE_URL}/analyze", json=payload)
    elapsed = time.time() - start

    if res.status_code != 200:
        print(f"   ❌ {lang_label} ({lang}): 실패 ({res.status_code})")
        return False

    data = res.json()
    print(f"\n   🌐 {lang_label} ({lang}) — {elapsed:.2f}초")
    print(f"      점수: {data['overall_score']}/100 | 판정: {data['overall_suitability']}")
    print(f"      위험 요약: {data['risk_summary'][:80]}...")

    # 메뉴명 확인 (한국어 + 번역 있는지)
    first_menu = data['menu_results'][0]
    print(f"      메뉴명 예시: {first_menu['menu_name']}")
    print(f"      메뉴 요약: {first_menu['summary'][:80]}...")

    return True


def test_query_language(lang: str, lang_label: str):
    """특정 언어로 문장 생성 테스트"""
    payload = {**QUERY_PAYLOAD_BASE, "language": lang}

    start = time.time()
    res = requests.post(f"{BASE_URL}/query", json=payload)
    elapsed = time.time() - start

    if res.status_code != 200:
        print(f"   ❌ {lang_label} ({lang}): 실패 ({res.status_code})")
        return False

    data = res.json()
    print(f"\n   🌐 {lang_label} ({lang}) — {elapsed:.2f}초")
    print(f"      소개 (한국어): {data['intro_text'][:60]}...")

    first_query = data['queries'][0]
    print(f"      상황 라벨: {first_query['situation_label']}")
    print(f"      한국어 문장: {first_query['korean_text'][:60]}...")
    print(f"      사용자 설명: {first_query['english_note'][:60]}...")
    print(f"      면책: {data['disclaimer'][:60]}...")

    return True


if __name__ == "__main__":
    print("\n🚀 K-Food Allergy Map — 다국어 테스트\n")

    # 서버 확인
    try:
        res = requests.get(f"{BASE_URL}/health")
        if res.status_code != 200:
            raise Exception()
    except:
        print("❌ 서버에 연결할 수 없습니다. uvicorn main:app --reload --port 8100")
        exit(1)

    # 캐시 초기화
    requests.post(f"{BASE_URL}/cache/clear")

    # 테스트할 언어 목록
    languages = [
        ("ko", "한국어"),
        ("en", "English"),
        ("ja", "日本語"),
        ("zh", "中文"),
    ]

    # 분석 테스트
    print_section("🔍 분석 다국어 테스트")
    for lang, label in languages:
        try:
            test_analyze_language(lang, label)
        except Exception as e:
            print(f"   ❌ {label}: 예외 — {e}")

    # 문장 생성 테스트
    print_section("📋 문장 생성 다국어 테스트")
    for lang, label in languages:
        try:
            test_query_language(lang, label)
        except Exception as e:
            print(f"   ❌ {label}: 예외 — {e}")

    print(f"\n{'=' * 60}")
    print("🏁 다국어 테스트 완료")
    print(f"{'=' * 60}\n")
