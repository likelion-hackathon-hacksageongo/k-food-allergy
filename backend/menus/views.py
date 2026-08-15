from rest_framework import generics, permissions
from .models import MenuItem
from .serializers import MenuItemSerializer


class MenuItemListView(generics.ListAPIView):
    """List menu items, optionally filtered by restaurant."""
    serializer_class = MenuItemSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        queryset = MenuItem.objects.all()
        restaurant_id = self.request.query_params.get('restaurant')
        if restaurant_id:
            queryset = queryset.filter(restaurant_id=restaurant_id)
        return queryset


class MenuItemDetailView(generics.RetrieveAPIView):
    """Retrieve a single menu item with allergen info."""
    serializer_class = MenuItemSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = MenuItem.objects.all()
