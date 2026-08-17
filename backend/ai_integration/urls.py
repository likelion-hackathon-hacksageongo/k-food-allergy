from django.urls import path

from .views import AnalyzeRestaurantView, GenerateQueryView

urlpatterns = [
    path('analyze/', AnalyzeRestaurantView.as_view(), name='ai-analyze'),
    path('query/', GenerateQueryView.as_view(), name='ai-query'),
]
