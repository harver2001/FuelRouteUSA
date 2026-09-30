import os
import csv
import time
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.db import transaction
from django.conf import settings
from api.models import TruckStop

US_STATES = {
    'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA',
    'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD',
    'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ',
    'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC',
    'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY', 'DC'
}

CUSTOM_OVERRIDES = {
    ('BROOKPARK', 'OH'): (41.4017, -81.8249),
    ('HENRICO', 'VA'): (37.5385, -77.3486),
    ('ELIZABETHPORT', 'NJ'): (40.6515, -74.1957),
    ('EVERGREEN', 'AL'): (31.4338, -86.9544),
}


class Command(BaseCommand):
    help = "Loads and geocodes truckstop fuel prices into the database."

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing truck stops before loading',
        )

    def handle(self, *args, **options):
        start_time = time.time()
        base_dir = settings.BASE_DIR

        # Candidate paths for files
        csv_paths = [
            base_dir / "data" / "fuel-prices-for-be-assessment.csv",
            base_dir / "fuel-prices-for-be-assessment.csv",
        ]
        csv_file = next((p for p in csv_paths if os.path.exists(p)), None)

        if not csv_file:
            self.stderr.write(self.style.ERROR("Fuel prices CSV not found!"))
            return

        self.stdout.write(self.style.NOTICE(f"Loading fuel data from: {csv_file}"))

        # Build coordinate lookup dictionary
        city_lookup = {}
        uscities_path = base_dir / "data" / "uscities.csv"
        extra_cities_path = base_dir / "data" / "us_cities_extra.csv"

        if os.path.exists(uscities_path):
            self.stdout.write("Reading primary US cities dataset...")
            with open(uscities_path, mode="r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for r in reader:
                    c = r["city"].strip().upper()
                    c_norm = c.replace(" ", "").replace("-", "").replace(".", "")
                    s = r["state_id"].strip().upper()
                    pop = float(r["population"]) if r.get("population") else 0
                    lat = float(r["lat"])
                    lng = float(r["lng"])
                    if (c, s) not in city_lookup or pop > city_lookup[(c, s)][2]:
                        city_lookup[(c, s)] = (lat, lng, pop)
                        city_lookup[(c_norm, s)] = (lat, lng, pop)

        if os.path.exists(extra_cities_path):
            self.stdout.write("Reading secondary US cities dataset...")
            with open(extra_cities_path, mode="r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for r in reader:
                    c = r["CITY"].strip().upper()
                    c_norm = c.replace(" ", "").replace("-", "").replace(".", "")
                    s = r["STATE_CODE"].strip().upper()
                    lat = float(r["LATITUDE"])
                    lng = float(r["LONGITUDE"])
                    if (c, s) not in city_lookup:
                        city_lookup[(c, s)] = (lat, lng, 0)
                        city_lookup[(c_norm, s)] = (lat, lng, 0)

        # Apply custom overrides
        for (c, s), coords in CUSTOM_OVERRIDES.items():
            city_lookup[(c, s)] = (coords[0], coords[1], 999999)

        self.stdout.write(f"Loaded {len(city_lookup)} city coordinate keys into memory.")

        # Read fuel prices CSV
        with open(csv_file, mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        self.stdout.write(f"Processing {len(rows)} truckstop records from CSV...")

        truck_stops_to_create = []
        skipped_non_us = 0
        unresolved = 0

        for r in rows:
            city_raw = r.get("City", "").strip()
            state_raw = r.get("State", "").strip()
            city_upper = city_raw.upper()
            state_upper = state_raw.upper()

            # Filter non-US states (e.g. Canadian provinces)
            if state_upper not in US_STATES:
                skipped_non_us += 1
                continue

            city_norm = city_upper.replace(" ", "").replace("-", "").replace(".", "")
            coords = city_lookup.get((city_upper, state_upper)) or city_lookup.get((city_norm, state_upper))

            if not coords:
                unresolved += 1
                continue

            lat, lng = coords[0], coords[1]

            try:
                opis_id = int(r["OPIS Truckstop ID"])
                name = r.get("Truckstop Name", "").strip()
                address = r.get("Address", "").strip()
                rack_id_raw = r.get("Rack ID", "").strip()
                rack_id = int(rack_id_raw) if rack_id_raw and rack_id_raw.isdigit() else None
                retail_price = Decimal(r["Retail Price"])
            except Exception as e:
                self.stderr.write(f"Error parsing row {r}: {e}")
                continue

            truck_stops_to_create.append(
                TruckStop(
                    opis_id=opis_id,
                    name=name,
                    address=address,
                    city=city_raw,
                    state=state_upper,
                    rack_id=rack_id,
                    retail_price=retail_price,
                    latitude=lat,
                    longitude=lng,
                )
            )

        self.stdout.write(f"Total US truckstops prepared: {len(truck_stops_to_create)}")
        self.stdout.write(f"Skipped non-US: {skipped_non_us}, Unresolved US: {unresolved}")

        # Clear existing records if requested or if already populated
        existing_count = TruckStop.objects.count()
        if existing_count > 0:
            self.stdout.write(f"Database currently has {existing_count} records. Clearing table...")
            TruckStop.objects.all().delete()

        # Batch insert
        self.stdout.write("Inserting records into SQLite...")
        with transaction.atomic():
            TruckStop.objects.bulk_create(truck_stops_to_create, batch_size=1000)

        elapsed = time.time() - start_time
        final_count = TruckStop.objects.count()
        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully ingested {final_count} truckstops in {elapsed:.2f} seconds!"
            )
        )
