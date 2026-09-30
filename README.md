# FuelRoute USA - Optimal Fuel Route Planner API & Interactive Map

A high-performance Django REST Framework API and interactive Leaflet.js web application that accepts start and finish locations anywhere within the Continental USA, computes the driving route via a single free routing API call (OSRM), identifies cost-optimal fuel stops from the provided truck stop dataset (accounting for a 500-mile vehicle range and 10 MPG fuel economy), and calculates the total money spent on fuel.

---

## 🌟 Key Features

- **Single External Routing Call**: Makes **exactly 1 network call** to OSRM to generate full route geometry, milestones, and driving duration.
- **Zero Paid API Keys**: Uses public OpenStreetMap routing (OSRM) and free map tile layers (OpenStreetMap, ESRI Street Map, ESRI Dark Canvas) — no credit card, paid tokens, or keys required.
- **Pre-Geocoded Offline Spatial Database**: 100% of US truck stops (7,531 stations) are geocoded offline into SQLite with spatial indexing.
- **Sub-5ms Corridor Search**: Uses an in-memory 3D Euclidean `scipy.spatial.cKDTree` to filter stations within a 10-mile corridor of the highway polyline.
- **Provably Optimal Fuel Stop Algorithm**:
  - Vehicle range: **500 miles**.
  - Fuel economy: **10 MPG** (0.1 gal/mile).
  - Tank capacity constraint: Max **50.0 gallons** per fill.
  - Invariant guarantee: Distance between stops $\le 500$ miles; total gallons pumped equals total fuel consumed ($D / 10$).
  - Minimizes total fuel cost (\$) by prioritizing cheaper stations in each sector.
- **Interactive Leaflet.js Map Dashboard**:
  - Live cyan route polyline and custom numbered fuel stop pins.
  - Interactive popups showing price (\$/gal), gallons pumped, cost, and highway mile marker.
  - Trip summary metric cards (Total Miles, Driving Time, Total Fuel Cost, Gallons Consumed, Optimal Stops, Avg Price).
  - Quick-preset US routes (NY → LA, Seattle → Miami, Dallas → Chicago, SF → Denver, Atlanta → Boston).
  - Layer switcher: OpenStreetMap, ESRI Street Map, and ESRI Dark Canvas.
- **Automated Test Suite**: 9 comprehensive unit and integration tests covering algorithmic invariants, boundary conditions, edge cases, and API endpoints.

---

## 🚀 Quickstart Guide

### 1. Prerequisites
- Python 3.11+
- Git

### 2. Activate Virtual Environment & Install Dependencies
```powershell
# In PowerShell (Windows)
.\venv\Scripts\activate

# Install requirements
pip install -r requirements.txt
```

### 3. Database Migration & Data Ingestion
```powershell
# Apply database migrations
python manage.py migrate

# Ingest and geocode all 7,531 US truck stops into SQLite (<1 second)
python manage.py load_fuel_data
```

### 4. Run the Development Server
```powershell
python manage.py runserver
```
Visit **[http://127.0.0.1:8000/](http://127.0.0.1:8000/)** in your web browser.

---

## 📡 REST API Documentation

### `GET /api/route/`
Calculates driving route, GeoJSON polyline, and cost-optimal fuel stops.

#### Query Parameters
| Parameter | Type | Required | Default | Description |
|---|---|---|---|---|
| `start` | string | **Yes** | — | City & State (e.g. `Dallas, TX`) or Coordinates (`32.7938,-96.7659`) |
| `finish` | string | **Yes** | — | City & State (e.g. `Chicago, IL`) or Coordinates (`41.8373,-87.6861`) |
| `corridor_miles` | float | No | `10.0` | Search radius in miles along highway polyline (1.0 to 30.0) |
| `mpg` | float | No | `10.0` | Vehicle fuel efficiency in miles per gallon |
| `range_miles` | float | No | `500.0` | Maximum vehicle range on a full tank in miles |

#### Example Request
```http
GET /api/route/?start=Dallas,TX&finish=Chicago,IL
```

#### Example Response
```json
{
  "start": {
    "query": "Dallas, TX",
    "display_name": "Dallas, TX",
    "latitude": 32.7938,
    "longitude": -96.7659
  },
  "finish": {
    "query": "Chicago, IL",
    "display_name": "Chicago, IL",
    "latitude": 41.8373,
    "longitude": -87.6861
  },
  "route_summary": {
    "total_distance_miles": 960.99,
    "total_duration_hours": 17.05,
    "total_duration_formatted": "17h 3m",
    "total_gallons_consumed": 96.1,
    "total_fuel_cost_usd": 273.12,
    "average_fuel_price_usd": 2.842,
    "fuel_efficiency_mpg": 10.0,
    "vehicle_range_miles": 500.0,
    "number_of_fuel_stops": 3
  },
  "fuel_stops": [
    {
      "id": 1421,
      "opis_id": 5512,
      "name": "CADOO MILLS",
      "address": "I-30, EXIT 83",
      "city": "Caddo Mills",
      "state": "TX",
      "retail_price": 2.8007,
      "latitude": 33.0567,
      "longitude": -96.2301,
      "mile_marker": 38.25,
      "distance_to_route_miles": 0.14,
      "gallons_pumped": 50.0,
      "fuel_cost_usd": 140.03,
      "step_reason": "Cheapest station in 500-mile range; filled tank to maximum capacity"
    },
    {
      "id": 2043,
      "opis_id": 6120,
      "name": "EXTRA MILE TRUCK STOP",
      "address": "I-30, EXIT 208",
      "city": "Hooks",
      "state": "TX",
      "retail_price": 2.8173,
      "latitude": 33.4735,
      "longitude": -94.2758,
      "mile_marker": 161.23,
      "distance_to_route_miles": 0.08,
      "gallons_pumped": 17.29,
      "fuel_cost_usd": 48.71,
      "step_reason": "Cheaper station found ahead at mile 172.9; bought fuel to reach it"
    },
    {
      "id": 4890,
      "opis_id": 8940,
      "name": "HUCKS FOOD & FUEL #379",
      "address": "I-57, EXIT 54",
      "city": "Marion",
      "state": "IL",
      "retail_price": 2.929,
      "latitude": 37.7306,
      "longitude": -88.9331,
      "mile_marker": 646.41,
      "distance_to_route_miles": 0.11,
      "gallons_pumped": 28.81,
      "fuel_cost_usd": 84.38,
      "step_reason": "Destination in range; purchased fuel required to complete journey"
    }
  ],
  "geojson": {
    "type": "LineString",
    "coordinates": [[-96.7659, 32.7938], [-96.7645, 32.7942], "..."]
  }
}
```

---

## 🧪 Running Automated Tests

Run the full Django test suite:
```powershell
python manage.py test api.tests
```

Test coverage includes:
- Short routes $< 500$ miles (verifies single optimal stop at cheapest station).
- Cross-country routes $> 2,000$ miles (verifies 500-mile gap invariant between all consecutive stops and destination).
- Bounded tank capacity invariants (verifies $\le 50$ gal pumped per stop).
- Fuel conservation invariant ($\sum \text{gallons} = \text{distance} / 10$).
- Cost minimization preference.
- Error handling for missing parameters and invalid locations.

---

## 🏗️ Architecture & Core Components

```
Django-Assignment/
├── api/
│   ├── models.py                     # TruckStop SQLite model with compound indexes
│   ├── views.py                      # RouteOptimizationAPIView & RouteMapView
│   ├── serializers.py                # DRF serializers for request/response validation
│   ├── urls.py                       # /api/route/ routing
│   ├── management/commands/
│   │   └── load_fuel_data.py         # Bulk geocoding & SQLite ingestion command
│   ├── services/
│   │   ├── geocoding_service.py      # Offline US cities DB + cached fallback
│   │   ├── routing_service.py        # OSRM Driving Engine integration (1 call)
│   │   ├── spatial_service.py        # cKDTree 3D spatial indexing (<5ms corridor query)
│   │   └── optimizer_service.py      # Optimal bounded-tank fuel algorithm
│   └── tests/
│       ├── test_optimizer.py         # Invariant & algorithm tests
│       └── test_api.py               # API integration tests
├── data/
│   ├── fuel-prices-for-be-assessment.csv  # 8,151 truck stops with retail prices
│   ├── uscities.csv                       # Primary US cities coordinate database
│   └── us_cities_extra.csv                # Secondary US cities coordinate dataset
├── fuel_planner/
│   ├── settings.py                   # Django 5.x settings + DRF + Whitenoise
│   └── urls.py                       # Root URL configuration
├── static/
│   ├── css/style.css                 # Dark glassmorphism responsive styling
│   └── js/app.js                     # Leaflet map controller & UI interactions
├── templates/
│   └── map.html                      # Interactive map dashboard template
└── requirements.txt                  # Python dependencies
```
