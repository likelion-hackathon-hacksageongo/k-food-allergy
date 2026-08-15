from django.urls import path
from .views import AllergyProfileView

urlpatterns = [
    path('me/', AllergyProfileView.as_view(), name='allergy-profile'),
]
