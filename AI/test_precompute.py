"""
사전 분석 (Pre-compute) 전체 흐름 테스트

서버 실행 필요:
    uvicorn main:app --reload --port 8100

사용법:
    python test_precompute.py
"""

import requests
import time

BASE_URL = "http://localhost:8100"
USER_ID = "test_user_01"

# 홍대 인근 가상 식당 5곳
RESTAURANTS = [
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
            {"id": 201, "name": "불고기", "description": "소고기, 간장", "ingredients": ["소고기", "간장", "배"]},
            {"id": 202, "name": "비빔냉면", "description": "메밀면, 고추장", "ingredients": ["메밀면", "고추장"]},
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
            {"id": 401, "name": "삼계탕", "description": "닭, 인삼", "ingredients": ["닭", "인삼", "찹쌀"]},
            {"id": 402, "name": "닭죽", "description": "닭, 쌀", "ingredients": ["닭", "쌀"]},
        ]
    },
    {
        "id": 5,
        "name": "상수돌솥밥",
        "category": "한식",
        "menu_items": [
            {"id": 501, "name": "돌솥비빔밥", "description": "밥, 나물, 고추장", "ingredients": ["밥", "나물", "고추장"]},
            {"id": 502, "name": "된장찌개 정식", "description": "된장찌개 + 밥", "ingredients": ["된장", "두부"]},
        ]
    },
]


def print_section(title):
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


def test_step1_empty_scores():
    """1단계: 사전 분석 전 — 빈 결과 확인"""
    print_section("1️⃣  사전 분석 전 — GET /scores (빈 결과)")

    # 이전 테스트 결과 정리
    import os
    from pathlib import Path
    scores_file = Path(__file__).parent / "data" / "scores" / f"{USER_ID}.json"
    if scores_file.exists():
        scores_file.unlink()
        print("   🧹 이전 결과 파일 삭제")

    res = requests.get(f"{BASE_URL}/scores/{USER_ID}")
    data = res.json()

    print(f"   상태: {res.status_code}")
    print(f"   결과: restaurants = {len(data.get('restaurants', {}))}")
    print(f"   computed_at: {data.get('computed_at')}")

    if res.status_code == 200 and len(data.get("restaurants", {})) == 0:
        print("   ✅ 예상대로 빈 결과")
        return True
    else:
        print("   ⚠️  빈 결과가 아님 (이전 캐시 남아있을 수 있음)")
        return True  # 계속 진행


def test_step2_trigger_precompute():
    """2단계: 사전 분석 트리거"""
    print_section("2️⃣  사전 분석 트리거 — POST /precompute/trigger")

    payload = {
        "user_id": USER_ID,
        "allergens": ["soy", "shellfish", "wheat"],
        "restaurants": RESTAURANTS,
        "language": "en",
    }

    start = time.time()
    res = requests.post(f"{BASE_URL}/precompute/trigger", json=payload)
    trigger_time = time.time() - start

    print(f"   상태: {res.status_code}")
    print(f"   응답 시간: {trigger_time:.3f}초")

    if res.status_code != 200:
        print(f"   ❌ 응답 내용: {res.text[:200]}")
        return False

    data = res.json()
    print(f"   메시지: {data.get('message', '')}")

    if trigger_time < 2.0:
        print("   ✅ 즉시 반환 확인 — 백그라운드 분석 진행 중")
    else:
        print(f"   ⚠️  반환 시간이 {trigger_time:.1f}초 — 즉시가 아닐 수 있음")

    return True


def test_step3_wait_and_check():
    """3단계: 분석 완료 대기 후 결과 확인"""
    print_section("3️⃣  분석 완료 대기 후 — GET /scores (결과 확인)")

    print("   ⏳ 분석 완료 대기 중 (최대 60초)...")

    # 폴링: 결과가 채워질 때까지 대기
    max_wait = 60
    interval = 3
    elapsed = 0

    while elapsed < max_wait:
        time.sleep(interval)
        elapsed += interval

        res = requests.get(f"{BASE_URL}/scores/{USER_ID}")
        data = res.json()
        count = len(data.get("restaurants", {}))

        print(f"      {elapsed}초 경과 — {count}/{len(RESTAURANTS)}개 완료")

        if count >= len(RESTAURANTS):
            break

    if count < len(RESTAURANTS):
        print(f"   ⚠️  시간 초과. {count}/{len(RESTAURANTS)}개만 완료.")
    else:
        print(f"   ✅ 전체 {count}개 식당 분석 완료!")

    return count > 0


def test_step4_instant_retrieval():
    """4단계: 즉시 조회 성능 확인"""
    print_section("4️⃣  즉시 조회 성능 — GET /scores (속도 측정)")

    # 10회 반복 측정
    times = []
    for _ in range(10):
        start = time.time()
        res = requests.get(f"{BASE_URL}/scores/{USER_ID}")
        times.append(time.time() - start)

    avg_ms = (sum(times) / len(times)) * 1000
    max_ms = max(times) * 1000

    data = res.json()
    restaurant_count = len(data.get("restaurants", {}))

    print(f"\n   📊 10회 조회 결과:")
    print(f"      평균: {avg_ms:.1f}ms")
    print(f"      최대: {max_ms:.1f}ms")
    print(f"      식당 수: {restaurant_count}개")

    print(f"\n   식당별 점수 (높은 순):")
    restaurants = data.get("restaurants", {})
    sorted_restaurants = sorted(restaurants.values(), key=lambda r: r["overall_score"], reverse=True)

    icons = {"safe": "✅", "caution": "⚠️", "avoid": "❌", "unknown": "❓"}
    for r in sorted_restaurants:
        icon = icons.get(r["overall_suitability"], "?")
        print(f"      {icon} {r['restaurant_name']}: {r['overall_score']}점 "
              f"(적합 {r['safe_menu_count']} / 주의 {r['caution_menu_count']} / 회피 {r['avoid_menu_count']})")

    if avg_ms < 500:
        print(f"\n   ✅ 평균 {avg_ms:.1f}ms — 지도 뷰에 충분한 속도!")
    else:
        print(f"\n   ⚠️  평균 {avg_ms:.1f}ms — 느림 (네트워크 오버헤드 포함)")
    return True


if __name__ == "__main__":
    print("\n🚀 K-Food Allergy Map — 사전 분석 전체 흐름 테스트\n")
    print(f"   사용자: {USER_ID}")
    print(f"   알레르겐: soy, shellfish, wheat")
    print(f"   식당: {len(RESTAURANTS)}곳")
    print(f"   언어: English")

    # 서버 확인
    try:
        res = requests.get(f"{BASE_URL}/health")
        assert res.status_code == 200
    except:
        print("\n❌ 서버에 연결할 수 없습니다. uvicorn main:app --reload --port 8100")
        exit(1)

    steps = [
        ("빈 결과 확인", test_step1_empty_scores),
        ("사전 분석 트리거", test_step2_trigger_precompute),
        ("분석 완료 대기", test_step3_wait_and_check),
        ("즉시 조회 성능", test_step4_instant_retrieval),
    ]

    results = []
    for name, fn in steps:
        try:
            success = fn()
            results.append((name, "✅ 성공" if success else "⚠️ 부분 성공"))
        except Exception as e:
            results.append((name, f"❌ 실패: {e}"))

    print_section("📊 테스트 결과 요약")
    for name, status in results:
        print(f"   {status} — {name}")

    print(f"\n🏁 완료\n")
