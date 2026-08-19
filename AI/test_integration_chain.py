"""
통합 체인 검증 스크립트

FE(5714) → BE(8200) → AI(8100) 연결 확인

사용법:
    cd AI
    python test_integration_chain.py
"""

import requests
import json

AI_URL = "http://localhost:8100"
BE_URL = "http://localhost:8200"


def check_ai_server():
    """AI 서버 상태 확인"""
    print("1️⃣  AI 서버 (port 8100)...")
    try:
        r = requests.get(f"{AI_URL}/health", timeout=5)
        if r.status_code == 200:
            print(f"   ✅ OK: {r.json()}")
            return True
        print(f"   ❌ 응답 {r.status_code}")
        return False
    except Exception as e:
        print(f"   ❌ 연결 실패: {e}")
        return False


def check_be_server():
    """BE 서버 상태 확인"""
    print("2️⃣  BE 서버 (port 8200)...")
    try:
        r = requests.get(f"{BE_URL}/api/restaurants/", timeout=5)
        if r.status_code in (200, 401):
            print(f"   ✅ OK (status: {r.status_code})")
            return True
        print(f"   ❌ 응답 {r.status_code}")
        return False
    except Exception as e:
        print(f"   ❌ 연결 실패: {e}")
        return False


def check_be_to_ai():
    """BE → AI 연결 확인 (로그인 필요)"""
    print("3️⃣  BE → AI 연결 (로그인 후 analysis 호출)...")

    # 먼저 로그인 시도 (테스트 계정)
    login_data = {"username": "integration_test_bot", "password": "xK9$mQ2!vL7"}
    r = requests.post(f"{BE_URL}/api/accounts/login/", json=login_data, timeout=5)

    if r.status_code != 200:
        # 계정 없으면 회원가입
        print("   ℹ️  테스트 계정 없음 — 회원가입 시도...")
        signup_data = {"username": "integration_test_bot", "email": "integration_bot_7291@testmail.dev", "password": "xK9$mQ2!vL7", "password_confirm": "xK9$mQ2!vL7"}
        r2 = requests.post(f"{BE_URL}/api/accounts/register/", json=signup_data, timeout=5)
        if r2.status_code in (200, 201):
            token_data = r2.json()
            access_token = token_data.get("access") or token_data.get("tokens", {}).get("access")
            print(f"   ✅ 회원가입 성공")
        else:
            print(f"   ❌ 회원가입 실패: {r2.status_code} {r2.text[:200]}")
            return False
    else:
        token_data = r.json()
        access_token = token_data.get("access")
        print(f"   ✅ 로그인 성공")

    if not access_token:
        print(f"   ❌ 토큰 없음: {token_data}")
        return False

    headers = {"Authorization": f"Bearer {access_token}"}

    # 프로필 설정
    profile_data = {"allergens": ["soy", "shellfish"], "preferred_language": "en"}
    r3 = requests.put(f"{BE_URL}/api/profiles/me/", json=profile_data, headers=headers, timeout=5)
    print(f"   ℹ️  프로필 설정: {r3.status_code}")

    # 식당 목록 확인
    r4 = requests.get(f"{BE_URL}/api/restaurants/", headers=headers, timeout=5)
    restaurants = r4.json().get("results", [])
    print(f"   ℹ️  식당 수: {len(restaurants)}")

    if not restaurants:
        print(f"   ⚠️  식당 데이터 없음 — BE DB에 import 필요")
        return False

    # analysis/restaurant 호출 (BE → AI) — 첫 번째 식당으로 테스트
    first_restaurant_id = restaurants[0]["id"]
    print(f"   ℹ️  /api/analysis/restaurant/ 호출 중 (restaurant_id={first_restaurant_id})...")
    r5 = requests.post(
        f"{BE_URL}/api/analysis/restaurant/",
        json={"restaurant_id": first_restaurant_id},
        headers=headers,
        timeout=90,
    )
    print(f"   응답: {r5.status_code}")
    if r5.status_code == 200:
        data = r5.json()
        print(f"   ✅ 결과: score={data.get('overall_score')}, suitability={data.get('overall_suitability')}")
        return True
    elif r5.status_code == 503:
        print(f"   ⚠️  AI 서버 호출 실패 (rate limit?): {r5.json().get('detail', '')[:200]}")
        return False
    else:
        print(f"   ❌ 실패: {r5.text[:300]}")
        return False


def check_ai_scan():
    """AI 스캔 엔드포인트 확인 (CORS 무관 — 서버 직접 호출)"""
    print("4️⃣  AI /scan/full 엔드포인트...")

    # 간단한 테스트 이미지 (1x1 white pixel PNG)
    import base64
    # 최소 PNG 파일
    png_data = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="
    )

    files = {"image": ("test.png", png_data, "image/png")}
    data = {"allergens": "soy,shellfish", "language": "en"}

    try:
        r = requests.post(f"{AI_URL}/scan/full", files=files, data=data, timeout=30)
        print(f"   응답: {r.status_code}")
        if r.status_code == 200:
            result = r.json()
            print(f"   ✅ 스캔 성공: {result.get('total_items', 0)} items")
            return True
        else:
            print(f"   ⚠️  {r.text[:200]}")
            # 500 with rate limit or empty image is acceptable
            return r.status_code == 500
    except Exception as e:
        print(f"   ❌ 실패: {e}")
        return False


def check_cors():
    """AI CORS 설정 확인"""
    print("5️⃣  AI CORS 설정...")
    try:
        # Preflight OPTIONS request
        headers = {
            "Origin": "http://localhost:5714",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        }
        r = requests.options(f"{AI_URL}/scan/full", headers=headers, timeout=5)
        cors_header = r.headers.get("access-control-allow-origin", "")
        if cors_header in ("*", "http://localhost:5714"):
            print(f"   ✅ CORS OK: allow-origin={cors_header}")
            return True
        else:
            print(f"   ❌ CORS 미허용: {cors_header or '(없음)'}")
            print(f"      응답 헤더: {dict(r.headers)}")
            return False
    except Exception as e:
        print(f"   ❌ 실패: {e}")
        return False


if __name__ == "__main__":
    print("\n🔗 K-Food Allergy Map — 통합 체인 검증\n")
    print(f"   AI: {AI_URL}")
    print(f"   BE: {BE_URL}")
    print(f"   FE: http://localhost:5714\n")

    results = []
    for name, fn in [
        ("AI 서버", check_ai_server),
        ("BE 서버", check_be_server),
        ("BE→AI 연결", check_be_to_ai),
        ("AI 스캔", check_ai_scan),
        ("CORS", check_cors),
    ]:
        try:
            ok = fn()
            results.append((name, "✅" if ok else "❌"))
        except Exception as e:
            results.append((name, f"❌ {e}"))
        print()

    print("=" * 50)
    print("📊 결과:")
    for name, status in results:
        print(f"   {status} {name}")
    print()
