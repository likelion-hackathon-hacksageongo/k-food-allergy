from rest_framework import generics, permissions
from .models import Restaurant
from .serializers import RestaurantListSerializer, RestaurantDetailSerializer


class RestaurantListView(generics.ListAPIView):
    """List all active restaurants in the area."""
    serializer_class = RestaurantListSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Restaurant.objects.filter(is_active=True)


class RestaurantDetailView(generics.RetrieveAPIView):
    """Retrieve a single restaurant's details."""
    serializer_class = RestaurantDetailSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Restaurant.objects.all()
