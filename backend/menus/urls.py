from django.urls import path
from .views import MenuItemListView, MenuItemDetailView

urlpatterns = [
    path('', MenuItemListView.as_view(), name='menu-list'),
    path('<int:pk>/', MenuItemDetailView.as_view(), name='menu-detail'),
]
