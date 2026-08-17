"""
AI 서비스 통합 테스트 스크립트

사용법:
    cd AI
    python test_services.py
"""

from schemas.types import (
    UserAllergyProfile,
    AllergenKey,
    RestaurantInput,
    MenuItemInput,
    QueryContext,
)
from services.analyzer import analyze_restaurant
from services.query_generator import generate_queries


def test_analyzer():
    """식당 분석 테스트 — 홍대 한식당 시나리오"""
    print("=" * 60)
    print("🔍 식당 분석 테스트")
    print("=" * 60)

    # 사용자: 대두, 갑각류, 밀 알레르기
    profile = UserAllergyProfile(
        allergens=[AllergenKey.SOY, AllergenKey.SHELLFISH, AllergenKey.WHEAT]
    )

    # 식당: 홍대 한솥밥 (가상 데이터)
    restaurant = RestaurantInput(
        id=1,
        name="홍대 한솥밥",
        category="한식",
        menu_items=[
            MenuItemInput(
                id=101,
                name="된장찌개",
                description="된장, 두부, 호박, 감자",
                ingredients=["된장", "두부", "호박", "감자", "청양고추"],
            ),
            MenuItemInput(
                id=102,
                name="김치찌개",
                description="김치, 돼지고기, 두부",
                ingredients=["김치", "돼지고기", "두부", "대파"],
            ),
            MenuItemInput(
                id=103,
                name="비빔밥",
                description="밥, 나물, 달걀, 고추장",
                ingredients=["밥", "시금치", "콩나물", "당근", "달걀", "고추장", "참기름"],
            ),
            MenuItemInput(
                id=104,
                name="삼겹살 구이",
                description="삼겹살, 쌈채소",
                ingredients=["삼겹살", "상추", "깻잎", "마늘"],
            ),
            MenuItemInput(
                id=105,
                name="해물파전",
                description="해물, 파, 밀가루 반죽",
                ingredients=["밀가루", "새우", "오징어", "파", "달걀"],
            ),
        ],
    )

    print(f"\n👤 사용자 알레르겐: {', '.join(a.value for a in profile.allergens)}")
    print(f"🏪 식당: {restaurant.name} (메뉴 {len(restaurant.menu_items)}개)")
    print("\n⏳ 분석 중...\n")

    result = analyze_restaurant(profile, restaurant)

    print(f"📊 전체 적합도 점수: {result.overall_score}/100")
    print(f"📋 전체 판정: {result.overall_suitability.value}")
    print(f"   ✅ 적합 가능: {result.safe_menu_count}개")
    print(f"   ⚠️  주의 필요: {result.caution_menu_count}개")
    print(f"   ❌ 회피 권장: {result.avoid_menu_count}개")
    print(f"\n💡 위험 요약: {result.risk_summary}")
    if result.cross_contamination_notes:
        print(f"⚠️  교차오염: {result.cross_contamination_notes}")

    print(f"\n{'─' * 40}")
    print("메뉴별 상세 결과:")
    print(f"{'─' * 40}")

    for menu in result.menu_results:
        icon = {"safe": "✅", "caution": "⚠️", "avoid": "❌", "unknown": "❓"}
        print(f"\n  {icon.get(menu.suitability.value, '?')} {menu.menu_name} [{menu.suitability.value}]")
        print(f"     정보 충분도: {menu.info_level.value}")
        print(f"     요약: {menu.summary}")
        if menu.allergen_details:
            for detail in menu.allergen_details:
                print(f"     - {detail.allergen}: {detail.likelihood} | {detail.source}")
        if menu.check_items:
            print(f"     확인 항목: {', '.join(menu.check_items)}")

    print(f"\n{'=' * 60}\n")
    return result


def test_query_generator():
    """문의 문장 생성 테스트"""
    print("=" * 60)
    print("📋 현장 문의 문장 생성 테스트")
    print("=" * 60)

    context = QueryContext(
        allergens=[AllergenKey.PEANUT, AllergenKey.SHELLFISH, AllergenKey.WHEAT],
        restaurant_name="홍대 한솥밥",
        menu_name="된장찌개",
        situations=["ingredient_check", "broth_sauce", "cross_contamination", "modification"],
    )

    print(f"\n👤 사용자 알레르겐: {', '.join(a.value for a in context.allergens)}")
    print(f"🏪 식당: {context.restaurant_name}")
    print(f"🍲 메뉴: {context.menu_name}")
    print(f"📌 상황: {', '.join(context.situations)}")
    print("\n⏳ 문장 생성 중...\n")

    result = generate_queries(context)

    print(f"💬 소개 문장:")
    print(f"   \"{result.intro_text}\"")

    print(f"\n{'─' * 40}")
    print("상황별 문의 문장:")
    print(f"{'─' * 40}")

    for query in result.queries:
        print(f"\n  📌 [{query.situation_label}]")
        print(f"     🇰🇷 {query.korean_text}")
        print(f"     🇬🇧 {query.english_note}")

    print(f"\n{'─' * 40}")
    print(f"⚠️  면책: {result.disclaimer}")
    print(f"\n{'=' * 60}\n")
    return result


if __name__ == "__main__":
    print("\n🚀 K-Food Allergy Map — AI 서비스 테스트 시작\n")

    try:
        analyzer_result = test_analyzer()
        print("✅ 식당 분석 테스트 성공!\n")
    except Exception as e:
        print(f"❌ 식당 분석 테스트 실패: {e}\n")

    try:
        query_result = test_query_generator()
        print("✅ 문장 생성 테스트 성공!\n")
    except Exception as e:
        print(f"❌ 문장 생성 테스트 실패: {e}\n")

    print("🏁 테스트 완료")
