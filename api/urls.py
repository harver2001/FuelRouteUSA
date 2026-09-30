from django.urls import path
from api.views import RouteOptimizationAPIView

app_name = "api"

urlpatterns = [
    path("route/", RouteOptimizationAPIView.as_view(), name="route-optimization"),
]
