"""
메뉴판 스캔 기능 테스트 스크립트

서버 실행 필요:
    uvicorn main:app --reload --port 8100

사용법:
    cd AI
    python test_scan.py <이미지 경로>
    python test_scan.py                  # 기본 테스트 이미지 사용

예시:
    python test_scan.py menu_photo.jpg
    python test_scan.py ../data/sample_menu.png
"""

import requests
import json
import sys
import time
from pathlib import Path

BASE_URL = "http://localhost:8100"


def print_section(title):
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


def test_scan_with_image(image_path: str, allergens: str = "soy,shellfish,wheat", language: str = "en"):
    """실제 이미지로 스캔 테스트"""
    print_section(f"📸 메뉴판 스캔 테스트")

    path = Path(image_path)
    if not path.exists():
        print(f"   ❌ 파일을 찾을 수 없습니다: {image_path}")
        return False

    file_size = path.stat().st_size / 1024
    print(f"   📄 파일: {path.name} ({file_size:.0f}KB)")
    print(f"   👤 알레르겐: {allergens}")
    print(f"   🌐 번역 언어: {language}")
    print(f"\n   ⏳ 스캔 중... (Vision API 호출)")

    start = time.time()
    with open(path, "rb") as f:
        res = requests.post(
            f"{BASE_URL}/scan",
            files={"image": (path.name, f, f"image/{path.suffix.lstrip('.')}")},
            data={"allergens": allergens, "language": language},
        )
    elapsed = time.time() - start

    if res.status_code != 200:
        print(f"   ❌ 실패 ({res.status_code}): {res.text[:300]}")
        return False

    data = res.json()
    print(f"   ⏱️  응답 시간: {elapsed:.2f}초")
    print(f"   🏪 식당명: {data.get('restaurant_name', '(인식 안 됨)')}")
    print(f"   📋 인식된 메뉴: {data['total_items']}개")

    print(f"\n   {'─' * 50}")
    print(f"   메뉴 목록:")
    print(f"   {'─' * 50}")

    safety_icons = {"safe": "✅", "caution": "🟡", "danger": "🔴", "unknown": "❓"}

    for item in data["menu_items"]:
        icon = safety_icons.get(item["safety_level"], "❓")
        print(f"\n   {icon} {item['original_text']}")
        print(f"      → {item['translated_name']}")
        if item["price"]:
            print(f"      💰 {item['price']}")
        if item["description"]:
            print(f"      📝 {item['description']}")
        if item["allergen_warnings"]:
            for warning in item["allergen_warnings"]:
                print(f"      ⚠️  {warning}")
        if item["allergen_keys"]:
            print(f"      🏷️  [{', '.join(item['allergen_keys'])}]")

    print(f"\n   {'─' * 50}")
    print(f"   ⚠️  {data['disclaimer']}")

    return True


def test_scan_without_allergens(image_path: str):
    """알레르겐 없이 순수 번역만 테스트"""
    print_section("🌐 순수 번역 테스트 (알레르겐 없음)")

    path = Path(image_path)
    if not path.exists():
        print(f"   ❌ 파일을 찾을 수 없습니다: {image_path}")
        return False

    print(f"   📄 파일: {path.name}")
    print(f"   🌐 번역 언어: Japanese (ja)")
    print(f"\n   ⏳ 스캔 중...")

    start = time.time()
    with open(path, "rb") as f:
        res = requests.post(
            f"{BASE_URL}/scan",
            files={"image": (path.name, f, f"image/{path.suffix.lstrip('.')}")},
            data={"allergens": "", "language": "ja"},
        )
    elapsed = time.time() - start

    if res.status_code != 200:
        print(f"   ❌ 실패 ({res.status_code}): {res.text[:300]}")
        return False

    data = res.json()
    print(f"   ⏱️  응답 시간: {elapsed:.2f}초")
    print(f"   📋 인식된 메뉴: {data['total_items']}개")

    for item in data["menu_items"][:5]:
        print(f"      {item['original_text']} → {item['translated_name']}")

    return True


def test_multilang_scan(image_path: str):
    """여러 언어로 번역 테스트"""
    print_section("🌍 다국어 번역 테스트")

    path = Path(image_path)
    if not path.exists():
        print(f"   ❌ 파일을 찾을 수 없습니다: {image_path}")
        return False

    languages = [("en", "English"), ("ja", "日本語"), ("zh", "中文")]

    for lang_code, lang_name in languages:
        with open(path, "rb") as f:
            res = requests.post(
                f"{BASE_URL}/scan",
                files={"image": (path.name, f, f"image/{path.suffix.lstrip('.')}")},
                data={"allergens": "soy,wheat", "language": lang_code},
            )

        if res.status_code != 200:
            print(f"   ❌ {lang_name}: 실패")
            continue

        data = res.json()
        first_item = data["menu_items"][0] if data["menu_items"] else None
        if first_item:
            print(f"   🌐 {lang_name}: {first_item['original_text']} → {first_item['translated_name']}")

    return True


if __name__ == "__main__":
    print("\n🚀 K-Food Allergy Map — 메뉴판 스캔 테스트\n")

    # 서버 확인
    try:
        res = requests.get(f"{BASE_URL}/health")
        assert res.status_code == 200
    except:
        print("❌ 서버에 연결할 수 없습니다.")
        print("   uvicorn main:app --reload --port 8100")
        exit(1)

    # 이미지 경로 결정
    if len(sys.argv) > 1:
        image_path = sys.argv[1]
    else:
        # 기본 테스트 이미지 찾기
        candidates = [
            "test_menu.jpg", "test_menu.png",
            "data/test_menu.jpg",
            "../data/sample_menu.jpg",
        ]
        image_path = None
        for c in candidates:
            if Path(c).exists():
                image_path = c
                break

        if not image_path:
            print("📌 사용법: python test_scan.py <메뉴판 이미지 경로>")
            print("")
            print("   예시:")
            print("   python test_scan.py menu_photo.jpg")
            print("   python test_scan.py C:\\Users\\photos\\menu.png")
            print("")
            print("   또는 Swagger UI에서 직접 테스트:")
            print("   http://localhost:8100/docs → POST /scan")
            exit(0)

    # 테스트 실행
    results = []

    try:
        success = test_scan_with_image(image_path, allergens="soy,shellfish,wheat", language="en")
        results.append(("영어 스캔 + 알레르겐", "✅ 성공" if success else "❌ 실패"))
    except Exception as e:
        results.append(("영어 스캔 + 알레르겐", f"❌ 예외: {e}"))

    # 결과 요약
    print_section("📊 테스트 결과")
    for name, status in results:
        print(f"   {status} — {name}")

    print(f"\n🏁 완료\n")
