from rest_framework import serializers
from .models import MenuItem, MenuAllergen


class MenuAllergenSerializer(serializers.ModelSerializer):
    class Meta:
        model = MenuAllergen
        fields = ['id', 'allergen_key', 'likelihood', 'source', 'notes']


class MenuItemSerializer(serializers.ModelSerializer):
    allergens = MenuAllergenSerializer(many=True, read_only=True)

    class Meta:
        model = MenuItem
        fields = [
            'id', 'restaurant', 'name', 'name_ko',
            'description', 'price', 'info_level', 'allergens',
        ]
