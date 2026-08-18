from django.urls import path

from .views import AnalyzeRestaurantView, GenerateQueryView

urlpatterns = [
    path('restaurant/', AnalyzeRestaurantView.as_view(), name='analysis-restaurant'),
    path('query/', GenerateQueryView.as_view(), name='analysis-query'),
]
