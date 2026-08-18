from rest_framework import serializers
from .models import Restaurant


class RestaurantListSerializer(serializers.ModelSerializer):
    class Meta:
        model = Restaurant
        fields = [
            'id', 'name', 'name_ko', 'address',
            'latitude', 'longitude', 'category',
            'source_type', 'is_active',
        ]


class RestaurantDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Restaurant
        fields = '__all__'
