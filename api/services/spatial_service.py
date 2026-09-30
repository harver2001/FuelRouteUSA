import math
import numpy as np
from scipy.spatial import cKDTree
from django.conf import settings
from api.models import TruckStop

EARTH_RADIUS_MILES = 3958.8


def latlon_to_xyz(lats, lons):
    """Converts arrays of latitude and longitude (in degrees) to 3D Cartesian coords on Earth sphere."""
    lats_rad = np.radians(lats)
    lons_rad = np.radians(lons)
    x = EARTH_RADIUS_MILES * np.cos(lats_rad) * np.cos(lons_rad)
    y = EARTH_RADIUS_MILES * np.cos(lats_rad) * np.sin(lons_rad)
    z = EARTH_RADIUS_MILES * np.sin(lats_rad)
    return np.column_stack((x, y, z))


def haversine_miles(lat1, lon1, lat2, lon2):
    """Vectorized or scalar Haversine distance in miles."""
    phi1, phi2 = np.radians(lat1), np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dlambda = np.radians(lon2 - lon1)
    a = np.sin(dphi / 2.0) ** 2 + np.cos(phi1) * np.cos(phi2) * np.sin(dlambda / 2.0) ** 2
    return 2.0 * EARTH_RADIUS_MILES * np.arctan2(np.sqrt(a), np.sqrt(1.0 - a))


class SpatialService:
    _instance = None
    _tree = None
    _truck_stops = None
    _xyz = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SpatialService, cls).__new__(cls)
            cls._instance._load_stops()
        return cls._instance

    def _load_stops(self):
        """Loads all truck stops from DB into memory and builds the 3D cKDTree."""
        stops_qs = TruckStop.objects.all().values(
            "id", "opis_id", "name", "address", "city", "state",
            "retail_price", "latitude", "longitude"
        )
        self._truck_stops = list(stops_qs)
        if not self._truck_stops:
            self._tree = None
            self._xyz = None
            return

        lats = np.array([s["latitude"] for s in self._truck_stops], dtype=np.float64)
        lons = np.array([s["longitude"] for s in self._truck_stops], dtype=np.float64)
        self._xyz = latlon_to_xyz(lats, lons)
        self._tree = cKDTree(self._xyz)

    def reload(self):
        """Reloads the spatial tree if the database changes."""
        self._load_stops()

    def find_stops_along_route(self, coordinates: list, corridor_radius_miles: float = 10.0) -> list:
        """
        Finds all truckstops within corridor_radius_miles of the route polyline.
        Each station is assigned:
          - mile_marker: exact cumulative distance from route start
          - distance_to_route: orthogonal/closest distance to the highway
        
        coordinates: list of [lon, lat] from OSRM GeoJSON LineString
        """
        if self._tree is None or not self._truck_stops:
            self._load_stops()
            if self._tree is None:
                return []

        if len(coordinates) < 2:
            return []

        route_coords = np.array(coordinates, dtype=np.float64)
        route_lons = route_coords[:, 0]
        route_lats = route_coords[:, 1]

        # Calculate cumulative distance along polyline vertices
        segment_dists = haversine_miles(
            route_lats[:-1], route_lons[:-1],
            route_lats[1:], route_lons[1:]
        )
        cumulative_dist = np.empty(len(coordinates), dtype=np.float64)
        cumulative_dist[0] = 0.0
        cumulative_dist[1:] = np.cumsum(segment_dists)
        total_route_length = cumulative_dist[-1]

        # Subsample route points if extremely dense (>4,000 points) to speed up KDTree query while maintaining coverage
        if len(coordinates) > 2000:
            step = max(1, len(coordinates) // 2000)
            sample_indices = np.arange(0, len(coordinates), step)
            if sample_indices[-1] != len(coordinates) - 1:
                sample_indices = np.append(sample_indices, len(coordinates) - 1)
        else:
            sample_indices = np.arange(len(coordinates))

        sampled_lats = route_lats[sample_indices]
        sampled_lons = route_lons[sample_indices]
        route_xyz = latlon_to_xyz(sampled_lats, sampled_lons)

        # Corridor query in 3D Euclidean space
        ball_results = self._tree.query_ball_point(route_xyz, r=corridor_radius_miles)
        candidate_stop_indices = set(idx for sublist in ball_results for idx in sublist)

        if not candidate_stop_indices:
            return []

        # For each candidate stop, find its closest projection onto the route polyline
        candidate_indices = np.array(list(candidate_stop_indices), dtype=np.int64)
        cand_xyz = self._xyz[candidate_indices]

        # Build KDTree for the full route vertices to find closest vertex for each candidate
        full_route_xyz = latlon_to_xyz(route_lats, route_lons)
        route_tree = cKDTree(full_route_xyz)
        dists, closest_vertex_indices = route_tree.query(cand_xyz)

        results = []
        for i, stop_idx in enumerate(candidate_indices):
            stop_data = self._truck_stops[stop_idx]
            dist_to_route = float(dists[i])

            if dist_to_route > corridor_radius_miles:
                continue

            v_idx = closest_vertex_indices[i]
            approx_mile = cumulative_dist[v_idx]

            # Refine mile marker by projecting onto adjacent segments [v_idx - 1, v_idx] and [v_idx, v_idx + 1]
            refined_mile = approx_mile
            cand_lat = stop_data["latitude"]
            cand_lon = stop_data["longitude"]

            best_seg_dist = dist_to_route
            for seg_start, seg_end in [(max(0, v_idx - 1), v_idx), (v_idx, min(len(coordinates) - 1, v_idx + 1))]:
                if seg_start == seg_end:
                    continue
                p1_lat, p1_lon = route_lats[seg_start], route_lons[seg_start]
                p2_lat, p2_lon = route_lats[seg_end], route_lons[seg_end]
                seg_len = segment_dists[seg_start]
                if seg_len < 1e-6:
                    continue

                # Project point onto 2D lat/lon locally
                dx = (p2_lon - p1_lon) * np.cos(np.radians(0.5 * (p1_lat + p2_lat)))
                dy = p2_lat - p1_lat
                pt_dx = (cand_lon - p1_lon) * np.cos(np.radians(0.5 * (p1_lat + cand_lat)))
                pt_dy = cand_lat - p1_lat

                seg_sq = dx * dx + dy * dy
                if seg_sq > 1e-12:
                    t = max(0.0, min(1.0, (pt_dx * dx + pt_dy * dy) / seg_sq))
                    proj_dist = cumulative_dist[seg_start] + t * seg_len
                    if 0.0 <= proj_dist <= total_route_length:
                        refined_mile = proj_dist

            results.append({
                "id": stop_data["id"],
                "opis_id": stop_data["opis_id"],
                "name": stop_data["name"],
                "address": stop_data["address"],
                "city": stop_data["city"],
                "state": stop_data["state"],
                "retail_price": float(stop_data["retail_price"]),
                "latitude": stop_data["latitude"],
                "longitude": stop_data["longitude"],
                "mile_marker": round(float(refined_mile), 2),
                "distance_to_route_miles": round(float(dist_to_route), 2),
            })

        # Sort candidate stops chronologically by their position along the route
        results.sort(key=lambda s: s["mile_marker"])
        return results
