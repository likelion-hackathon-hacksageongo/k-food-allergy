"""
URL configuration for K-Food Allergy Map project.
"""

from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/accounts/', include('accounts.urls')),
    path('api/profiles/', include('profiles.urls')),
    path('api/restaurants/', include('restaurants.urls')),
    path('api/menus/', include('menus.urls')),
    path('api/feedback/', include('feedback.urls')),
]
