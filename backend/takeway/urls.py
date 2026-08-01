"""
URL configuration for takeway project.
"""

from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)

api_v1_patterns = [
    path("auth/", include("accounts.urls")),
    path("locations/", include("locations.urls")),
    path("", include("businesses.urls")),
    path("", include("orders.urls")),
    path("", include("technicians.urls")),
    path("", include("rides.urls")),
    path("", include("notifications.urls")),
    path("", include("common.urls")),
    # API schema endpoints
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include((api_v1_patterns, "v1"))),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
