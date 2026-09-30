import time
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.views.generic import TemplateView

from api.services.geocoding_service import GeocodingService
from api.services.routing_service import RoutingService
from api.services.spatial_service import SpatialService
from api.services.optimizer_service import OptimizerService
from api.serializers import RouteOptimizationResponseSerializer


def format_duration(total_minutes: int) -> str:
    hours = total_minutes // 60
    mins = total_minutes % 60
    if hours > 0:
        return f"{hours}h {mins}m"
    return f"{mins}m"


class RouteOptimizationAPIView(APIView):
    """
    Calculates driving route and cost-optimal fuel stops across the USA.
    Accepts GET query params or POST JSON:
      - start: e.g. "Dallas, TX" or "32.7767,-96.7970"
      - finish: e.g. "Chicago, IL" or "41.8781,-87.6298"
      - corridor_miles: optional float (default: 10.0)
      - mpg: optional float (default: 10.0)
      - range_miles: optional float (default: 500.0)
    """

    def get(self, request, *args, **kwargs):
        return self._process_request(request.query_params)

    def post(self, request, *args, **kwargs):
        return self._process_request(request.data)

    def _process_request(self, data):
        start_query = data.get("start")
        finish_query = data.get("finish")

        if not start_query or not finish_query:
            return Response(
                {
                    "error": "Both 'start' and 'finish' parameters are required.",
                    "example": "/api/route/?start=New+York,NY&finish=Los+Angeles,CA",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        corridor_miles = float(data.get("corridor_miles", 10.0))
        corridor_miles = max(1.0, min(30.0, corridor_miles))

        mpg = float(data.get("mpg", 10.0))
        tank_range = float(data.get("range_miles", 500.0))

        # 1. Geocode Start and Finish
        geocoder = GeocodingService()
        try:
            start_geo = geocoder.geocode(str(start_query))
        except ValueError as e:
            return Response({"error": f"Invalid start location: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            finish_geo = geocoder.geocode(str(finish_query))
        except ValueError as e:
            return Response({"error": f"Invalid finish location: {str(e)}"}, status=status.HTTP_400_BAD_REQUEST)

        # 2. Get Driving Route from OSRM (Exactly 1 network call)
        try:
            route_data = RoutingService.get_route(
                start_lat=start_geo["latitude"],
                start_lon=start_geo["longitude"],
                finish_lat=finish_geo["latitude"],
                finish_lon=finish_geo["longitude"],
            )
        except RuntimeError as e:
            return Response({"error": f"Routing service error: {str(e)}"}, status=status.HTTP_502_BAD_GATEWAY)

        total_distance = route_data["total_distance_miles"]
        duration_minutes = route_data["total_duration_minutes"]
        duration_hours = route_data["total_duration_hours"]
        coordinates = route_data["coordinates"]

        # 3. Spatial Search: Find candidate truck stops within corridor
        spatial = SpatialService()
        candidate_stops = spatial.find_stops_along_route(
            coordinates=coordinates,
            corridor_radius_miles=corridor_miles,
        )

        # 4. Optimal Fuel Stops Optimization
        plan = OptimizerService.optimize(
            total_distance_miles=total_distance,
            candidate_stops=candidate_stops,
            tank_capacity_miles=tank_range,
            mpg=mpg,
        )

        total_cost = plan["total_fuel_cost"]
        total_gallons = plan["total_gallons"]
        avg_price = round(total_cost / total_gallons, 4) if total_gallons > 0 else 0.0

        response_payload = {
            "start": {
                "query": str(start_query),
                "display_name": start_geo["display_name"],
                "latitude": start_geo["latitude"],
                "longitude": start_geo["longitude"],
            },
            "finish": {
                "query": str(finish_query),
                "display_name": finish_geo["display_name"],
                "latitude": finish_geo["latitude"],
                "longitude": finish_geo["longitude"],
            },
            "route_summary": {
                "total_distance_miles": total_distance,
                "total_duration_hours": duration_hours,
                "total_duration_formatted": format_duration(duration_minutes),
                "total_gallons_consumed": total_gallons,
                "total_fuel_cost_usd": total_cost,
                "average_fuel_price_usd": avg_price,
                "fuel_efficiency_mpg": mpg,
                "vehicle_range_miles": tank_range,
                "number_of_fuel_stops": plan["number_of_stops"],
            },
            "fuel_stops": plan["stops"],
            "geojson": route_data["geojson"],
        }

        serializer = RouteOptimizationResponseSerializer(data=response_payload)
        if serializer.is_valid():
            return Response(serializer.data, status=status.HTTP_200_OK)
        else:
            # Fallback direct return if serializer issues
            return Response(response_payload, status=status.HTTP_200_OK)


class RouteMapView(TemplateView):
    """Interactive Leaflet.js dashboard UI."""
    template_name = "map.html"
