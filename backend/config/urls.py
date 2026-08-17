"""
URL configuration for K-Food Allergy Map project.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

urlpatterns = [
    path('admin/', admin.site.urls),

    # API docs
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('swagger/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),

    # App endpoints
    path('api/accounts/', include('accounts.urls')),
    path('api/profiles/', include('profiles.urls')),
    path('api/restaurants/', include('restaurants.urls')),
    path('api/menus/', include('menus.urls')),
    path('api/feedback/', include('feedback.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
