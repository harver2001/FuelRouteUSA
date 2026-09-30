from django.contrib import admin
from django.urls import path, include
from api.views import RouteMapView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('api.urls')),
    path('', RouteMapView.as_view(), name='map-dashboard'),
]
