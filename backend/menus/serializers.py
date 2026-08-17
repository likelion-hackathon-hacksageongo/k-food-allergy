from rest_framework import serializers
from profiles.models import AllergyProfile
from .models import MenuItem, MenuAllergen
from .matching import evaluate_menu_item


class MenuAllergenSerializer(serializers.ModelSerializer):
    class Meta:
        model = MenuAllergen
        fields = ['id', 'allergen_key', 'likelihood', 'source', 'notes']


class MenuItemSerializer(serializers.ModelSerializer):
    allergens = MenuAllergenSerializer(many=True, read_only=True)
    personalized = serializers.SerializerMethodField()

    class Meta:
        model = MenuItem
        fields = [
            'id', 'restaurant', 'name', 'name_ko',
            'description', 'price', 'info_level', 'allergens', 'personalized',
        ]

    def get_personalized(self, obj):
        """
        Verdict for the current logged-in user, based on their allergy
        profile: {"status", "label", "reasons"}, or None if they have no
        profile set up yet.
        """
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return None
        try:
            profile = request.user.allergy_profile
        except AllergyProfile.DoesNotExist:
            return None
        return evaluate_menu_item(obj, set(profile.allergens))
