from rest_framework import serializers
from .models import AllergyProfile, AllergenChoice


class AllergyProfileSerializer(serializers.ModelSerializer):
    allergens = serializers.ListField(
        child=serializers.ChoiceField(choices=AllergenChoice.choices),
    )

    class Meta:
        model = AllergyProfile
        fields = ['id', 'allergens', 'preferred_language', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']
