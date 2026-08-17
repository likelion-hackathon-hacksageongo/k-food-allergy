"""
AI API 서버 HTTP 테스트 스크립트

사전 조건:
    uvicorn main:app --reload --port 8100  (별도 터미널에서 실행)

사용법:
    cd AI
    python test_api.py
"""

import requests
import json
import time

BASE_URL = "http://localhost:8100"


def print_section(title):
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


def test_health():
    """서버 상태 확인"""
    print_section("🏥 Health Check")

    try:
        res = requests.get(f"{BASE_URL}/health")
        res.raise_for_status()
        print(f"   ✅ 상태: {res.json()}")
        return True
    except requests.ConnectionError:
        print(f"   ❌ 서버에 연결할 수 없습니다.")
        print(f"      다른 터미널에서 먼저 실행하세요:")
        print(f"      uvicorn main:app --reload --port 8100")
        return False


def test_analyze():
    """식당 분석 API 테스트"""
    print_section("🔍 POST /analyze — 식당 분석")

    payload = {
        "allergens": ["soy", "shellfish", "wheat"],
        "restaurant": {
            "id": 1,
            "name": "홍대 한솥밥",
            "category": "한식",
            "menu_items": [
                {
                    "id": 101,
                    "name": "된장찌개",
                    "description": "된장, 두부, 호박, 감자",
                    "ingredients": ["된장", "두부", "호박", "감자"]
                },
                {
                    "id": 102,
                    "name": "김치찌개",
                    "description": "김치, 돼지고기, 두부",
                    "ingredients": ["김치", "돼지고기", "두부", "대파"]
                },
                {
                    "id": 103,
                    "name": "비빔밥",
                    "description": "밥, 나물, 달걀, 고추장",
                    "ingredients": ["밥", "시금치", "콩나물", "달걀", "고추장"]
                },
                {
                    "id": 104,
                    "name": "삼겹살 구이",
                    "description": "삼겹살, 쌈채소",
                    "ingredients": ["삼겹살", "상추", "깻잎", "마늘"]
                },
                {
                    "id": 105,
                    "name": "해물파전",
                    "description": "해물, 파, 밀가루 반죽",
                    "ingredients": ["밀가루", "새우", "오징어", "파", "달걀"]
                }
            ]
        }
    }

    print(f"\n   👤 알레르겐: {payload['allergens']}")
    print(f"   🏪 식당: {payload['restaurant']['name']} ({len(payload['restaurant']['menu_items'])}개 메뉴)")
    print(f"\n   ⏳ 분석 요청 중...")

    start = time.time()
    res = requests.post(f"{BASE_URL}/analyze", json=payload)
    elapsed = time.time() - start

    if res.status_code != 200:
        print(f"   ❌ 실패 ({res.status_code}): {res.text}")
        return False

    data = res.json()
    print(f"   ⏱️  응답 시간: {elapsed:.2f}초")
    print(f"\n   📊 결과:")
    print(f"      전체 점수: {data['overall_score']}/100")
    print(f"      판정: {data['overall_suitability']}")
    print(f"      ✅ 적합: {data['safe_menu_count']}개")
    print(f"      ⚠️  주의: {data['caution_menu_count']}개")
    print(f"      ❌ 회피: {data['avoid_menu_count']}개")
    print(f"      💡 요약: {data['risk_summary']}")

    print(f"\n   메뉴별:")
    icons = {"safe": "✅", "caution": "⚠️", "avoid": "❌", "unknown": "❓"}
    for m in data['menu_results']:
        print(f"      {icons.get(m['suitability'], '?')} {m['menu_name']}: {m['summary']}")

    return True


def test_query():
    """문의 문장 생성 API 테스트"""
    print_section("📋 POST /query — 문의 문장 생성")

    payload = {
        "allergens": ["peanut", "shellfish", "wheat"],
        "restaurant_name": "홍대 한솥밥",
        "menu_name": "된장찌개",
        "situations": ["ingredient_check", "broth_sauce", "cross_contamination", "modification"]
    }

    print(f"\n   👤 알레르겐: {payload['allergens']}")
    print(f"   🏪 식당: {payload['restaurant_name']}")
    print(f"   🍲 메뉴: {payload['menu_name']}")
    print(f"   📌 상황: {payload['situations']}")
    print(f"\n   ⏳ 문장 생성 중...")

    start = time.time()
    res = requests.post(f"{BASE_URL}/query", json=payload)
    elapsed = time.time() - start

    if res.status_code != 200:
        print(f"   ❌ 실패 ({res.status_code}): {res.text}")
        return False

    data = res.json()
    print(f"   ⏱️  응답 시간: {elapsed:.2f}초")
    print(f"\n   💬 소개: \"{data['intro_text']}\"")

    print(f"\n   상황별 문장:")
    for q in data['queries']:
        print(f"      📌 [{q['situation_label']}]")
        print(f"         🇰🇷 {q['korean_text']}")
        print(f"         🇬🇧 {q['english_note']}")

    return True


def test_batch():
    """일괄 분석 API 테스트 — 지도 뷰 시나리오"""
    print_section("🗺️  POST /analyze/batch — 지도 일괄 분석")

    # 홍대 인근 가상 식당 5곳
    restaurants = [
        {
            "id": 1,
            "name": "홍대 한솥밥",
            "category": "한식",
            "menu_items": [
                {"id": 101, "name": "된장찌개", "description": "된장, 두부, 호박", "ingredients": ["된장", "두부"]},
                {"id": 102, "name": "삼겹살 구이", "description": "삼겹살, 쌈채소", "ingredients": ["삼겹살", "상추"]},
            ]
        },
        {
            "id": 2,
            "name": "마포불고기",
            "category": "한식",
            "menu_items": [
                {"id": 201, "name": "불고기", "description": "소고기, 간장양념", "ingredients": ["소고기", "간장", "배"]},
                {"id": 202, "name": "비빔냉면", "description": "냉면, 고추장", "ingredients": ["메밀면", "고추장"]},
            ]
        },
        {
            "id": 3,
            "name": "연남동 순두부",
            "category": "한식",
            "menu_items": [
                {"id": 301, "name": "순두부찌개", "description": "순두부, 해물", "ingredients": ["순두부", "새우", "조개"]},
                {"id": 302, "name": "김치전", "description": "김치, 밀가루", "ingredients": ["김치", "밀가루", "달걀"]},
            ]
        },
        {
            "id": 4,
            "name": "홍대삼계탕",
            "category": "한식",
            "menu_items": [
                {"id": 401, "name": "삼계탕", "description": "닭, 인삼, 찹쌀", "ingredients": ["닭", "인삼", "찹쌀"]},
                {"id": 402, "name": "닭죽", "description": "닭, 쌀", "ingredients": ["닭", "쌀", "참기름"]},
            ]
        },
        {
            "id": 5,
            "name": "상수돌솥밥",
            "category": "한식",
            "menu_items": [
                {"id": 501, "name": "돌솥비빔밥", "description": "밥, 나물, 고추장", "ingredients": ["밥", "나물", "고추장", "달걀"]},
                {"id": 502, "name": "된장찌개 정식", "description": "된장찌개 + 밥", "ingredients": ["된장", "두부", "밥"]},
            ]
        },
    ]

    payload = {
        "allergens": ["soy", "shellfish", "wheat"],
        "restaurants": restaurants,
    }

    print(f"\n   👤 알레르겐: {payload['allergens']}")
    print(f"   🏪 식당: {len(restaurants)}곳")
    print(f"\n   ⏳ 일괄 분석 중 (병렬 처리)...")

    start = time.time()
    res = requests.post(f"{BASE_URL}/analyze/batch", json=payload)
    elapsed = time.time() - start

    if res.status_code != 200:
        print(f"   ❌ 실패 ({res.status_code}): {res.text[:200]}")
        return False

    data = res.json()
    print(f"   ⏱️  응답 시간: {elapsed:.2f}초 ({len(restaurants)}곳 동시 분석)")
    print(f"   📊 API 호출: {data['api_call_count']}건 | 캐시 히트: {data['cached_count']}건")

    print(f"\n   식당별 점수 (높은 순):")
    icons = {"safe": "✅", "caution": "⚠️", "avoid": "❌", "unknown": "❓"}
    for r in data['results']:
        print(f"      {icons.get(r['overall_suitability'], '?')} {r['restaurant_name']}: "
              f"{r['overall_score']}점 | 적합 {r['safe_menu_count']} / 주의 {r['caution_menu_count']} / 회피 {r['avoid_menu_count']}")

    return True


def test_cache_performance():
    """캐시 성능 테스트 — 동일 요청 2회 호출 비교"""
    print_section("⚡ 캐시 성능 테스트")

    # 캐시 초기화
    requests.post(f"{BASE_URL}/cache/clear")

    payload = {
        "allergens": ["peanut", "dairy"],
        "restaurant": {
            "id": 99,
            "name": "캐시 테스트 식당",
            "category": "한식",
            "menu_items": [
                {"id": 991, "name": "제육볶음", "description": "돼지고기, 고추장", "ingredients": ["돼지고기", "고추장"]},
                {"id": 992, "name": "계란말이", "description": "달걀, 파", "ingredients": ["달걀", "파"]},
            ]
        }
    }

    # 1차 호출 (API)
    start = time.time()
    res1 = requests.post(f"{BASE_URL}/analyze", json=payload)
    first_call = time.time() - start

    # 2차 호출 (캐시)
    start = time.time()
    res2 = requests.post(f"{BASE_URL}/analyze", json=payload)
    second_call = time.time() - start

    if res1.status_code != 200 or res2.status_code != 200:
        print(f"   ❌ 요청 실패")
        return False

    score1 = res1.json()["overall_score"]
    score2 = res2.json()["overall_score"]

    print(f"\n   1차 호출 (OpenAI API): {first_call:.2f}초")
    print(f"   2차 호출 (캐시 히트):  {second_call:.4f}초")
    print(f"   ⚡ 속도 향상: {first_call / max(second_call, 0.001):.0f}x")
    print(f"   결과 일치: {'✅' if score1 == score2 else '❌'} (점수: {score1})")

    # 캐시 통계 확인
    stats = requests.get(f"{BASE_URL}/cache/stats").json()
    print(f"\n   📈 캐시 통계: {stats}")

    return True


def test_error_handling():
    """에러 처리 테스트"""
    print_section("⚠️  에러 처리 테스트")

    # 빈 메뉴
    payload = {
        "allergens": ["soy"],
        "restaurant": {
            "id": 99,
            "name": "빈식당",
            "category": "한식",
            "menu_items": []
        }
    }

    res = requests.post(f"{BASE_URL}/analyze", json=payload)
    print(f"   빈 메뉴 요청: {res.status_code} — ", end="")
    if res.status_code == 422:
        print("✅ 올바르게 거부됨 (validation error)")
    elif res.status_code == 400:
        print(f"✅ 올바르게 거부됨: {res.json().get('detail', '')}")
    else:
        print(f"❓ 예상치 못한 응답: {res.text[:100]}")

    # 잘못된 알레르겐
    payload2 = {
        "allergens": ["invalid_allergen"],
        "restaurant_name": "테스트",
        "situations": ["ingredient_check"]
    }

    res2 = requests.post(f"{BASE_URL}/query", json=payload2)
    print(f"   잘못된 알레르겐: {res2.status_code} — ", end="")
    if res2.status_code == 422:
        print("✅ 올바르게 거부됨 (validation error)")
    else:
        print(f"❓ 예상치 못한 응답: {res2.text[:100]}")

    return True
if __name__ == "__main__":
    print("\n🚀 K-Food Allergy Map — API 서버 테스트")
    print(f"   대상: {BASE_URL}")

    if not test_health():
        print("\n🛑 서버가 실행되지 않아 테스트를 중단합니다.")
        exit(1)

    results = []

    for name, fn in [
        ("식당 분석", test_analyze),
        ("문장 생성", test_query),
        ("일괄 분석 (batch)", test_batch),
        ("캐시 성능", test_cache_performance),
        ("에러 처리", test_error_handling),
    ]:
        try:
            success = fn()
            results.append((name, "✅ 성공" if success else "❌ 실패"))
        except Exception as e:
            results.append((name, f"❌ 예외: {e}"))

    print_section("📊 테스트 결과 요약")
    for name, status in results:
        print(f"   {status} — {name}")

    print(f"\n🏁 완료\n")
