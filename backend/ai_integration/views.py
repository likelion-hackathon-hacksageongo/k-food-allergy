from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from profiles.models import AllergyProfile
from restaurants.models import Restaurant
from menus.models import MenuItem

from .client import analyze_restaurant, generate_query, AIServiceError

# NOTE: this is a direct, synchronous proxy to the AI server (see
# AI/INTEGRATION_GUIDE.md section 4 "방법 A"). It does NOT use their
# precompute/scores endpoints yet - each call re-runs the LLM analysis
# live (a few seconds). Wiring up precompute-on-profile-save + a fast
# /scores read is a follow-up once this path is confirmed working end
# to end with the real AI server + an OpenAI key.


def _restaurant_payload(restaurant: Restaurant) -> dict:
    """
    Build the AI service's expected restaurant shape from our DB.
    We don't store a separate `ingredients` list (see MenuItem.description),
    so we best-effort split description on commas as a stand-in; the AI
    service treats `ingredients` as optional anyway.
    """
    return {
        'id': restaurant.id,
        'name': restaurant.name_ko or restaurant.name,
        'category': restaurant.category,
        'menu_items': [
            {
                'id': item.id,
                'name': item.name_ko or item.name,
                'description': item.description,
                'ingredients': [s.strip() for s in item.description.split(',') if s.strip()],
            }
            for item in restaurant.menu_items.all()
        ],
    }


class AnalyzeRestaurantView(APIView):
    """
    POST /api/ai/analyze/
    Body: {"restaurant_id": 1}

    Looks up the logged-in user's allergy profile and the restaurant's
    menu from our DB, calls the AI service's POST /analyze, and relays
    its result as-is (menu-by-menu suitability + restaurant overall_score).
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        restaurant_id = request.data.get('restaurant_id')
        if not restaurant_id:
            return Response({'detail': 'restaurant_id is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            profile = request.user.allergy_profile
        except AllergyProfile.DoesNotExist:
            return Response(
                {'detail': '알레르기 프로필을 먼저 등록해주세요.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        restaurant = Restaurant.objects.filter(pk=restaurant_id).prefetch_related('menu_items').first()
        if restaurant is None:
            return Response({'detail': 'Restaurant not found.'}, status=status.HTTP_404_NOT_FOUND)

        try:
            result = analyze_restaurant(
                allergens=profile.allergens,
                restaurant=_restaurant_payload(restaurant),
                language=profile.preferred_language,
            )
        except AIServiceError as e:
            return Response({'detail': str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        return Response(result)


class GenerateQueryView(APIView):
    """
    POST /api/ai/query/
    Body: {"restaurant_id": 1, "menu_item_id": 101 (optional), "situations": [...]}

    situations defaults to ["ingredient_check"] if omitted. See
    AI/INTEGRATION_GUIDE.md for the full situation code list.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        restaurant_id = request.data.get('restaurant_id')
        menu_item_id = request.data.get('menu_item_id')
        situations = request.data.get('situations') or ['ingredient_check']

        if not restaurant_id:
            return Response({'detail': 'restaurant_id is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            profile = request.user.allergy_profile
        except AllergyProfile.DoesNotExist:
            return Response(
                {'detail': '알레르기 프로필을 먼저 등록해주세요.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        restaurant = Restaurant.objects.filter(pk=restaurant_id).first()
        if restaurant is None:
            return Response({'detail': 'Restaurant not found.'}, status=status.HTTP_404_NOT_FOUND)

        menu_name = None
        if menu_item_id:
            menu_item = MenuItem.objects.filter(pk=menu_item_id, restaurant=restaurant).first()
            if menu_item is None:
                return Response({'detail': 'Menu item not found on this restaurant.'}, status=status.HTTP_404_NOT_FOUND)
            menu_name = menu_item.name_ko or menu_item.name

        try:
            result = generate_query(
                allergens=profile.allergens,
                restaurant_name=restaurant.name_ko or restaurant.name,
                menu_name=menu_name,
                situations=situations,
                language=profile.preferred_language,
            )
        except AIServiceError as e:
            return Response({'detail': str(e)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        return Response(result)
