import os
import sys
from pathlib import Path
import django
BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fuel_planner.settings')
django.setup()

from api.services.geocoding_service import GeocodingService
from api.services.routing_service import RoutingService
from api.services.spatial_service import SpatialService
from api.services.optimizer_service import OptimizerService

def run_tests():
    routes = [
        ("Dallas, TX", "Houston, TX"),
        ("Dallas, TX", "Chicago, IL"),
        ("New York, NY", "Los Angeles, CA"),
    ]

    for start, finish in routes:
        print(f"\n==========================================")
        print(f"Route: {start} -> {finish}")
        p1 = GeocodingService().geocode(start)
        p2 = GeocodingService().geocode(finish)
        r = RoutingService.get_route(p1["latitude"], p1["longitude"], p2["latitude"], p2["longitude"])
        D = r["total_distance_miles"]
        candidate_stops = SpatialService().find_stops_along_route(r["coordinates"])
        
        opt = OptimizerService.optimize(D, candidate_stops)
        print(f"Total distance: {D} miles")
        print(f"Candidate stops in corridor: {len(candidate_stops)}")
        print(f"Optimal stops chosen: {opt['number_of_stops']}")
        print(f"Total gallons: {opt['total_gallons']} (Expected: {round(D/10.0, 2)})")
        print(f"Total cost: ${opt['total_fuel_cost']}")
        
        # Verify invariants
        prev_mile = 0.0
        for s in opt["stops"]:
            mile = float(s["mile_marker"])
            gap = mile - prev_mile
            assert gap <= 500.0, f"Gap {gap} exceeds 500 miles!"
            print(f"  Stop @ mile {mile:.1f} (gap: {gap:.1f} mi): {s['name']} in {s['city']}, {s['state']} | {s['gallons_pumped']} gal @ ${s['retail_price']:.3f}/gal = ${s['fuel_cost']}")
            prev_mile = mile
        finish_gap = D - prev_mile
        assert finish_gap <= 500.0, f"Final gap {finish_gap} exceeds 500 miles!"
        print(f"  Final leg to destination: {finish_gap:.1f} miles (<= 500 miles OK)")

if __name__ == "__main__":
    run_tests()
