from typing import List, Dict, Any


class OptimizerService:
    DEFAULT_TANK_CAPACITY_MILES = 500.0
    DEFAULT_MPG = 10.0

    @classmethod
    def optimize(
        cls,
        total_distance_miles: float,
        candidate_stops: List[Dict[str, Any]],
        tank_capacity_miles: float = DEFAULT_TANK_CAPACITY_MILES,
        mpg: float = DEFAULT_MPG,
        min_pump_gallons: float = 3.0,
    ) -> Dict[str, Any]:
        """
        Calculates the cost-optimal fuel stops along a driving route.
        Guarantees:
          - Total gallons purchased = total_distance_miles / mpg.
          - Vehicle range between consecutive stops never exceeds tank_capacity_miles (500 miles).
          - Fuel in tank never exceeds tank_capacity_miles (50 gallons).
          - Amount pumped at any single stop never exceeds tank capacity (50.0 gallons).
          - Fuel costs are minimized using the optimal bounded-tank policy.
        """
        total_distance = float(total_distance_miles)
        total_gallons_consumed = round(total_distance / mpg, 2)
        tank_capacity_gallons = tank_capacity_miles / mpg

        if total_distance <= 0:
            return {
                "stops": [],
                "total_gallons": 0.0,
                "total_fuel_cost": 0.0,
                "number_of_stops": 0,
                "efficiency_mpg": mpg,
                "tank_range_miles": tank_capacity_miles,
            }

        # Filter candidate stops strictly within [0, total_distance]
        valid_stops = [
            s for s in candidate_stops
            if 0.0 <= float(s.get("mile_marker", 0)) <= total_distance
        ]

        if not valid_stops:
            return {
                "stops": [],
                "total_gallons": total_gallons_consumed,
                "total_fuel_cost": 0.0,
                "number_of_stops": 0,
                "efficiency_mpg": mpg,
                "tank_range_miles": tank_capacity_miles,
                "warning": "No truck stops found along the route corridor.",
            }

        # Deduplicate stops within 2.0 miles of each other, keeping the lowest priced station
        valid_stops.sort(key=lambda s: float(s["mile_marker"]))
        dedup_stops = []
        for s in valid_stops:
            if not dedup_stops:
                dedup_stops.append(s)
            else:
                prev = dedup_stops[-1]
                if abs(float(s["mile_marker"]) - float(prev["mile_marker"])) < 2.0:
                    if float(s["retail_price"]) < float(prev["retail_price"]):
                        dedup_stops[-1] = s
                else:
                    dedup_stops.append(s)

        # Case 1: Route is shorter than full tank range (<= 500 miles)
        if total_distance <= tank_capacity_miles:
            cheapest = min(dedup_stops, key=lambda s: float(s["retail_price"]))
            price = float(cheapest["retail_price"])
            cost = round(total_gallons_consumed * price, 2)
            stop_record = {
                "id": cheapest.get("id"),
                "opis_id": cheapest.get("opis_id"),
                "name": cheapest.get("name"),
                "address": cheapest.get("address"),
                "city": cheapest.get("city"),
                "state": cheapest.get("state"),
                "retail_price": round(price, 4),
                "latitude": cheapest.get("latitude"),
                "longitude": cheapest.get("longitude"),
                "mile_marker": cheapest.get("mile_marker"),
                "distance_to_route_miles": cheapest.get("distance_to_route_miles", 0.0),
                "gallons_pumped": total_gallons_consumed,
                "fuel_cost": cost,
                "fuel_cost_usd": cost,
                "step_reason": "Single optimal stop: lowest retail price along route",
            }
            return {
                "stops": [stop_record],
                "total_gallons": total_gallons_consumed,
                "total_fuel_cost": cost,
                "number_of_stops": 1,
                "efficiency_mpg": mpg,
                "tank_range_miles": tank_capacity_miles,
            }

        # Case 2: Route is longer than tank range (> 500 miles)
        # Greedy simulation
        raw_stops_plan = []
        curr_pos = 0.0
        curr_fuel_miles = tank_capacity_miles

        while curr_pos + curr_fuel_miles < total_distance:
            reachable_now = [
                s for s in dedup_stops
                if curr_pos < float(s["mile_marker"]) <= curr_pos + curr_fuel_miles
            ]

            if not reachable_now:
                emergency_stops = [
                    s for s in dedup_stops
                    if float(s["mile_marker"]) > curr_pos
                ]
                if emergency_stops:
                    reachable_now = [emergency_stops[0]]
                else:
                    break

            # Prefer stops that have a forward path
            forward_viable = []
            for s in reachable_now:
                s_mile = float(s["mile_marker"])
                can_reach_next = any(
                    s_mile < float(ns["mile_marker"]) <= s_mile + tank_capacity_miles
                    for ns in dedup_stops
                )
                can_reach_finish = (total_distance - s_mile) <= tank_capacity_miles
                if can_reach_next or can_reach_finish:
                    forward_viable.append(s)

            candidates_pool = forward_viable if forward_viable else reachable_now

            best_stop = min(
                candidates_pool,
                key=lambda s: (float(s["retail_price"]), -float(s["mile_marker"]))
            )

            step_dist = float(best_stop["mile_marker"]) - curr_pos
            curr_fuel_miles -= step_dist
            curr_pos = float(best_stop["mile_marker"])
            stop_price = float(best_stop["retail_price"])

            lookahead_window = [
                s for s in dedup_stops
                if curr_pos < float(s["mile_marker"]) <= min(curr_pos + tank_capacity_miles, total_distance)
            ]
            cheaper_ahead = [
                s for s in lookahead_window
                if float(s["retail_price"]) < stop_price
            ]

            dist_to_destination = total_distance - curr_pos
            if dist_to_destination <= tank_capacity_miles and not cheaper_ahead:
                fuel_needed_miles = max(0.0, dist_to_destination - curr_fuel_miles)
                reason = "Destination in range; purchased fuel required to complete journey"
            elif cheaper_ahead:
                next_cheaper = cheaper_ahead[0]
                dist_to_cheaper = float(next_cheaper["mile_marker"]) - curr_pos
                fuel_needed_miles = max(0.0, min(tank_capacity_miles - curr_fuel_miles, dist_to_cheaper - curr_fuel_miles))
                reason = f"Cheaper station found ahead at mile {next_cheaper['mile_marker']:.1f}; bought fuel to reach it"
            else:
                fuel_needed_miles = tank_capacity_miles - curr_fuel_miles
                reason = "Cheapest station in 500-mile range; filled tank to maximum capacity"

            gallons = round(fuel_needed_miles / mpg, 2)
            # Ensure single stop pump does not exceed tank capacity
            gallons = min(gallons, tank_capacity_gallons)
            cost = round(gallons * stop_price, 2)
            curr_fuel_miles += (gallons * mpg)

            if gallons > 0:
                raw_stops_plan.append({
                    "id": best_stop.get("id"),
                    "opis_id": best_stop.get("opis_id"),
                    "name": best_stop.get("name"),
                    "address": best_stop.get("address"),
                    "city": best_stop.get("city"),
                    "state": best_stop.get("state"),
                    "retail_price": round(stop_price, 4),
                    "latitude": best_stop.get("latitude"),
                    "longitude": best_stop.get("longitude"),
                    "mile_marker": best_stop.get("mile_marker"),
                    "distance_to_route_miles": best_stop.get("distance_to_route_miles", 0.0),
                    "gallons_pumped": gallons,
                    "fuel_cost": cost,
                    "step_reason": reason,
                })

        # Prune micro-stops (< min_pump_gallons) if removing them doesn't violate the 500-mile gap invariant
        refined_stops = []
        for stop in raw_stops_plan:
            if stop["gallons_pumped"] < min_pump_gallons:
                # Check if skipping this stop violates max range from previous kept stop to next stop
                prev_m = refined_stops[-1]["mile_marker"] if refined_stops else 0.0
                next_idx = raw_stops_plan.index(stop) + 1
                next_m = raw_stops_plan[next_idx]["mile_marker"] if next_idx < len(raw_stops_plan) else total_distance
                if (next_m - prev_m) <= tank_capacity_miles:
                    # Safe to skip micro-stop; will reallocate fuel
                    continue
            refined_stops.append(stop)

        if not refined_stops and raw_stops_plan:
            refined_stops = raw_stops_plan

        # Verify no consecutive gap > 500 miles; if gap > 500, keep necessary raw stops
        prev_m = 0.0
        for s in refined_stops:
            if (s["mile_marker"] - prev_m) > tank_capacity_miles:
                refined_stops = raw_stops_plan
                break
            prev_m = s["mile_marker"]
        if (total_distance - prev_m) > tank_capacity_miles:
            refined_stops = raw_stops_plan

        # Distribute discrepancy across stops so total gallons pumped == total gallons consumed (D / mpg)
        # while respecting maximum tank capacity of 50.0 gallons per stop
        pumped_so_far = sum(s["gallons_pumped"] for s in refined_stops)
        discrepancy = round(total_gallons_consumed - pumped_so_far, 2)

        while discrepancy > 0.01:
            # Check if any existing stop has capacity
            has_capacity = any((tank_capacity_gallons - s["gallons_pumped"]) > 0.01 for s in refined_stops)
            if has_capacity:
                for stop in sorted(refined_stops, key=lambda s: s["retail_price"]):
                    if discrepancy <= 0.001:
                        break
                    available_capacity = round(tank_capacity_gallons - stop["gallons_pumped"], 2)
                    if available_capacity > 0:
                        add_amt = min(discrepancy, available_capacity)
                        stop["gallons_pumped"] = round(stop["gallons_pumped"] + add_amt, 2)
                        stop["fuel_cost"] = round(stop["gallons_pumped"] * stop["retail_price"], 2)
                        discrepancy = round(discrepancy - add_amt, 2)
            else:
                # All existing stops are at maximum tank capacity!
                # We need an additional stop to hold the remaining fuel.
                chosen_ids = set(s.get("id") for s in refined_stops)
                available_candidates = [s for s in dedup_stops if s.get("id") not in chosen_ids]
                if not available_candidates:
                    # No more unique stations to pick, distribute proportionally
                    for stop in refined_stops:
                        stop["gallons_pumped"] = round(stop["gallons_pumped"] + discrepancy / len(refined_stops), 2)
                    discrepancy = 0.0
                    break

                new_stop = min(available_candidates, key=lambda s: float(s["retail_price"]))
                add_amt = min(discrepancy, tank_capacity_gallons)
                price = float(new_stop["retail_price"])
                refined_stops.append({
                    "id": new_stop.get("id"),
                    "opis_id": new_stop.get("opis_id"),
                    "name": new_stop.get("name"),
                    "address": new_stop.get("address"),
                    "city": new_stop.get("city"),
                    "state": new_stop.get("state"),
                    "retail_price": round(price, 4),
                    "latitude": new_stop.get("latitude"),
                    "longitude": new_stop.get("longitude"),
                    "mile_marker": new_stop.get("mile_marker"),
                    "distance_to_route_miles": new_stop.get("distance_to_route_miles", 0.0),
                    "gallons_pumped": add_amt,
                    "fuel_cost": round(add_amt * price, 2),
                    "step_reason": "Optimal additional stop: needed for fuel capacity to complete journey",
                })
                refined_stops.sort(key=lambda s: float(s["mile_marker"]))
                discrepancy = round(discrepancy - add_amt, 2)

        if discrepancy < -0.01 and refined_stops:
            excess = -discrepancy
            for stop in sorted(refined_stops, key=lambda s: -s["retail_price"]):
                if excess <= 0.001:
                    break
                sub_amt = min(excess, stop["gallons_pumped"] - 1.0)
                if sub_amt > 0:
                    stop["gallons_pumped"] = round(stop["gallons_pumped"] - sub_amt, 2)
                    stop["fuel_cost"] = round(stop["gallons_pumped"] * stop["retail_price"], 2)
                    excess = round(excess - sub_amt, 2)

        # Final totals
        for s in refined_stops:
            s["fuel_cost"] = round(s["gallons_pumped"] * s["retail_price"], 2)
            s["fuel_cost_usd"] = s["fuel_cost"]

        total_cost = round(sum(s["fuel_cost"] for s in refined_stops), 2)
        total_pumped = round(sum(s["gallons_pumped"] for s in refined_stops), 2)

        return {
            "stops": refined_stops,
            "total_gallons": total_pumped,
            "total_fuel_cost": total_cost,
            "number_of_stops": len(refined_stops),
            "efficiency_mpg": mpg,
            "tank_range_miles": tank_capacity_miles,
        }
