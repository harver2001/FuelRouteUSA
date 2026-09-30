from rest_framework import serializers


class LocationSerializer(serializers.Serializer):
    query = serializers.CharField()
    display_name = serializers.CharField()
    latitude = serializers.FloatField()
    longitude = serializers.FloatField()


class RouteSummarySerializer(serializers.Serializer):
    total_distance_miles = serializers.FloatField()
    total_duration_hours = serializers.FloatField()
    total_duration_formatted = serializers.CharField()
    total_gallons_consumed = serializers.FloatField()
    total_fuel_cost_usd = serializers.FloatField()
    average_fuel_price_usd = serializers.FloatField()
    fuel_efficiency_mpg = serializers.FloatField()
    vehicle_range_miles = serializers.FloatField()
    number_of_fuel_stops = serializers.IntegerField()


class FuelStopSerializer(serializers.Serializer):
    id = serializers.IntegerField(required=False)
    opis_id = serializers.IntegerField(required=False)
    name = serializers.CharField()
    address = serializers.CharField()
    city = serializers.CharField()
    state = serializers.CharField()
    retail_price = serializers.FloatField()
    latitude = serializers.FloatField()
    longitude = serializers.FloatField()
    mile_marker = serializers.FloatField()
    distance_to_route_miles = serializers.FloatField()
    gallons_pumped = serializers.FloatField()
    fuel_cost_usd = serializers.FloatField(source="fuel_cost")
    step_reason = serializers.CharField(required=False)


class RouteOptimizationResponseSerializer(serializers.Serializer):
    start = LocationSerializer()
    finish = LocationSerializer()
    route_summary = RouteSummarySerializer()
    fuel_stops = FuelStopSerializer(many=True)
    geojson = serializers.DictField()
