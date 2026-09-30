import requests

METERS_TO_MILES = 0.000621371
SECONDS_TO_HOURS = 1.0 / 3600.0


class RoutingService:
    OSRM_BASE_URL = "http://router.project-osrm.org/route/v1/driving"

    @classmethod
    def get_route(cls, start_lat: float, start_lon: float, finish_lat: float, finish_lon: float) -> dict:
        """
        Calculates driving route between two points using OSRM.
        Makes exactly 1 HTTP request to OSRM.
        
        OSRM coordinate format in URL: {lon},{lat};{lon},{lat}
        """
        url = f"{cls.OSRM_BASE_URL}/{start_lon},{start_lat};{finish_lon},{finish_lat}?overview=full&geometries=geojson"

        try:
            response = requests.get(url, timeout=15)
        except requests.exceptions.Timeout:
            raise RuntimeError("OSRM routing service timed out. Please try again.")
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Failed to communicate with routing service: {str(e)}")

        if response.status_code != 200:
            raise RuntimeError(f"Routing service returned HTTP status {response.status_code}: {response.text}")

        data = response.json()
        if data.get("code") != "Ok" or not data.get("routes"):
            msg = data.get("message", "No route found between the specified locations.")
            raise RuntimeError(f"Routing failed: {msg}")

        route = data["routes"][0]
        distance_meters = float(route["distance"])
        duration_seconds = float(route["duration"])

        distance_miles = round(distance_meters * METERS_TO_MILES, 2)
        duration_hours = round(duration_seconds * SECONDS_TO_HOURS, 2)
        duration_minutes = int(round(duration_seconds / 60))

        geometry = route.get("geometry", {})
        # OSRM coordinates are [lon, lat]
        coordinates = geometry.get("coordinates", [])

        if not coordinates:
            raise RuntimeError("OSRM route contained no geometry coordinates.")

        return {
            "total_distance_miles": distance_miles,
            "total_duration_hours": duration_hours,
            "total_duration_minutes": duration_minutes,
            "geojson": geometry,
            "coordinates": coordinates,  # List of [lon, lat]
        }
