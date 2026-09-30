from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from api.models import TruckStop


class RouteAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        # Seed test truck stops
        TruckStop.objects.create(
            opis_id=101,
            name="TEST STOP NORTH",
            address="100 Highway Rd",
            city="Wilmer",
            state="TX",
            retail_price=2.75,
            latitude=32.5898,
            longitude=-96.6853,
        )
        TruckStop.objects.create(
            opis_id=102,
            name="TEST STOP SOUTH",
            address="200 Highway Rd",
            city="Corsicana",
            state="TX",
            retail_price=2.85,
            latitude=32.0954,
            longitude=-96.4689,
        )

    def test_missing_parameters_returns_400(self):
        url = reverse("api:route-optimization")
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)

        # Missing finish
        response = self.client.get(url, {"start": "Dallas, TX"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_location_returns_400(self):
        url = reverse("api:route-optimization")
        # Coordinates outside continental US
        response = self.client.get(url, {"start": "51.5074,-0.1278", "finish": "48.8566,2.3522"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)

        # Unresolvable location
        response = self.client.get(url, {"start": "NonExistentPlaceXYZ99999", "finish": "Dallas, TX"})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)

    def test_valid_get_route(self):
        url = reverse("api:route-optimization")
        response = self.client.get(url, {"start": "Dallas, TX", "finish": "Houston, TX"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        data = response.data
        self.assertIn("start", data)
        self.assertIn("finish", data)
        self.assertIn("route_summary", data)
        self.assertIn("fuel_stops", data)
        self.assertIn("geojson", data)

        summary = data["route_summary"]
        self.assertGreater(summary["total_distance_miles"], 200.0)
        self.assertGreater(summary["total_duration_hours"], 3.0)
        self.assertGreater(summary["total_fuel_cost_usd"], 0.0)
        self.assertEqual(summary["fuel_efficiency_mpg"], 10.0)
        self.assertEqual(summary["vehicle_range_miles"], 500.0)

        # Invariant: total gallons consumed equals distance / 10
        expected_gallons = round(summary["total_distance_miles"] / 10.0, 2)
        self.assertAlmostEqual(summary["total_gallons_consumed"], expected_gallons, delta=0.1)

    def test_valid_post_route(self):
        url = reverse("api:route-optimization")
        payload = {
            "start": "32.7938,-96.7659",
            "finish": "29.7604,-95.3698",
        }
        response = self.client.post(url, payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("route_summary", response.data)
        self.assertEqual(response.data["start"]["latitude"], 32.7938)
        self.assertEqual(response.data["finish"]["latitude"], 29.7604)
