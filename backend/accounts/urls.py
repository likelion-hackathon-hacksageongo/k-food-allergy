from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .views import RegisterView

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    # Stock TokenObtainPairView: login with `username` (the ID chosen at
    # registration) + `password`, not email.
    path('login/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
]
