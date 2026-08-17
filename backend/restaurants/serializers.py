from rest_framework import serializers
from profiles.models import AllergyProfile
from menus.matching import evaluate_restaurant
from .models import Restaurant


class PersonalizedRestaurantMixin:
    """
    Adds a `personalized` field: this restaurant's headline verdict + a
    safe/warning/unconfirmed/danger breakdown across its menu items, for
    the current logged-in user's allergy profile. None if not logged in
    or no profile set up yet.
    """

    def get_personalized(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return None
        try:
            profile = request.user.allergy_profile
        except AllergyProfile.DoesNotExist:
            return None
        menu_items = obj.menu_items.prefetch_related('allergens').all()
        return evaluate_restaurant(menu_items, set(profile.allergens))


class RestaurantListSerializer(PersonalizedRestaurantMixin, serializers.ModelSerializer):
    personalized = serializers.SerializerMethodField()

    class Meta:
        model = Restaurant
        fields = [
            'id', 'name', 'name_ko', 'address',
            'latitude', 'longitude', 'category', 'phone',
            'source_type', 'is_active', 'personalized',
        ]


class RestaurantDetailSerializer(PersonalizedRestaurantMixin, serializers.ModelSerializer):
    personalized = serializers.SerializerMethodField()

    class Meta:
        model = Restaurant
        fields = '__all__'
