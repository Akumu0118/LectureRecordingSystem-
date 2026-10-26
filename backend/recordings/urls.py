from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import RecordingViewSet, health

router = DefaultRouter()
router.register("recordings", RecordingViewSet, basename="recording")

urlpatterns = [
    path("health/", health),
    path("", include(router.urls)),
]
