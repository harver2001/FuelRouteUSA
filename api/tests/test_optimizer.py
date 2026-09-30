from django.test import TestCase
from api.services.optimizer_service import OptimizerService


class OptimizerServiceTests(TestCase):
    def test_short_route_under_500_miles(self):
        """Routes <= 500 miles should select the single cheapest station along the route."""
        total_dist = 300.0
        candidate_stops = [
            {"id": 1, "name": "Stop Expensive", "city": "City A", "state": "TX", "retail_price": 3.85, "mile_marker": 50.0, "latitude": 30.0, "longitude": -95.0},
            {"id": 2, "name": "Stop Cheapest", "city": "City B", "state": "TX", "retail_price": 2.75, "mile_marker": 150.0, "latitude": 31.0, "longitude": -96.0},
            {"id": 3, "name": "Stop Moderate", "city": "City C", "state": "TX", "retail_price": 3.10, "mile_marker": 250.0, "latitude": 32.0, "longitude": -97.0},
        ]

        result = OptimizerService.optimize(total_dist, candidate_stops, tank_capacity_miles=500.0, mpg=10.0)

        self.assertEqual(result["number_of_stops"], 1)
        self.assertEqual(result["total_gallons"], 30.0)  # 300 / 10
        self.assertEqual(result["stops"][0]["name"], "Stop Cheapest")
        self.assertEqual(result["stops"][0]["retail_price"], 2.75)
        self.assertAlmostEqual(result["total_fuel_cost"], 30.0 * 2.75, places=2)

    def test_long_route_gap_invariant(self):
        """Cross-country routes must never exceed 500 miles between consecutive stops or start/finish."""
        total_dist = 2200.0
        # Create stations every 100 miles
        candidate_stops = []
        for m in range(100, 2200, 100):
            candidate_stops.append({
                "id": m,
                "name": f"Stop @ {m}",
                "city": "Sample",
                "state": "US",
                "retail_price": 3.00 + (m % 5) * 0.1,
                "mile_marker": float(m),
                "latitude": 35.0,
                "longitude": -100.0,
            })

        result = OptimizerService.optimize(total_dist, candidate_stops, tank_capacity_miles=500.0, mpg=10.0)

        self.assertGreater(result["number_of_stops"], 1)
        self.assertEqual(result["total_gallons"], 220.0)  # 2200 / 10

        prev_marker = 0.0
        for s in result["stops"]:
            mile = float(s["mile_marker"])
            gap = mile - prev_marker
            self.assertLessEqual(gap, 500.0, f"Gap {gap} between {prev_marker} and {mile} exceeds 500 miles!")
            self.assertLessEqual(s["gallons_pumped"], 50.0, f"Stop at {mile} pumped {s['gallons_pumped']} gal, exceeding 50-gal capacity!")
            prev_marker = mile

        final_gap = total_dist - prev_marker
        self.assertLessEqual(final_gap, 500.0, f"Final gap {final_gap} exceeds 500 miles!")

    def test_total_gallons_conservation(self):
        """Total gallons pumped must equal total_distance / mpg."""
        distances = [120.0, 480.0, 950.0, 1600.0, 2800.0]
        for dist in distances:
            candidate_stops = [
                {
                    "id": i,
                    "name": f"Station {i}",
                    "city": "City",
                    "state": "ST",
                    "retail_price": 2.80 + (i % 7) * 0.05,
                    "mile_marker": float(i * 150),
                    "latitude": 33.0,
                    "longitude": -90.0,
                }
                for i in range(1, int(dist // 150) + 1)
            ]
            res = OptimizerService.optimize(dist, candidate_stops, tank_capacity_miles=500.0, mpg=10.0)
            expected_gallons = round(dist / 10.0, 2)
            self.assertEqual(res["total_gallons"], expected_gallons)

    def test_cost_optimality_preference(self):
        """Algorithm should prefer significantly cheaper stations in the corridor."""
        total_dist = 800.0
        candidate_stops = [
            {"id": 1, "name": "Stop Cheap 1", "city": "C1", "state": "TX", "retail_price": 2.50, "mile_marker": 350.0, "latitude": 30.0, "longitude": -95.0},
            {"id": 2, "name": "Stop Expensive 1", "city": "C2", "state": "TX", "retail_price": 4.50, "mile_marker": 360.0, "latitude": 30.0, "longitude": -95.0},
            {"id": 3, "name": "Stop Cheap 2", "city": "C3", "state": "TX", "retail_price": 2.60, "mile_marker": 700.0, "latitude": 31.0, "longitude": -96.0},
            {"id": 4, "name": "Stop Expensive 2", "city": "C4", "state": "TX", "retail_price": 4.60, "mile_marker": 710.0, "latitude": 31.0, "longitude": -96.0},
        ]
        result = OptimizerService.optimize(total_dist, candidate_stops, tank_capacity_miles=500.0, mpg=10.0)
        chosen_names = [s["name"] for s in result["stops"]]
        self.assertIn("Stop Cheap 1", chosen_names)
        self.assertNotIn("Stop Expensive 1", chosen_names)

    def test_empty_candidates_handling(self):
        """Should handle missing candidate stops gracefully."""
        result = OptimizerService.optimize(500.0, [])
        self.assertEqual(result["number_of_stops"], 0)
        self.assertEqual(result["total_fuel_cost"], 0.0)
