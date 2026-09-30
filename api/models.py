from django.db import models


class TruckStop(models.Model):
    opis_id = models.IntegerField(db_index=True, help_text="OPIS Truckstop ID")
    name = models.CharField(max_length=255, help_text="Truckstop Name")
    address = models.CharField(max_length=255, help_text="Address / Highway Exit")
    city = models.CharField(max_length=100, db_index=True, help_text="City")
    state = models.CharField(max_length=10, db_index=True, help_text="State code (e.g. TX, CA)")
    rack_id = models.IntegerField(null=True, blank=True, help_text="Rack ID")
    retail_price = models.DecimalField(max_digits=8, decimal_places=4, db_index=True, help_text="Retail Price per gallon in USD")
    latitude = models.FloatField(db_index=True, help_text="WGS84 Latitude")
    longitude = models.FloatField(db_index=True, help_text="WGS84 Longitude")

    class Meta:
        db_table = "truck_stops"
        verbose_name = "Truck Stop"
        verbose_name_plural = "Truck Stops"
        indexes = [
            models.Index(fields=["state", "city"], name="idx_state_city"),
            models.Index(fields=["latitude", "longitude"], name="idx_lat_lng"),
            models.Index(fields=["retail_price"], name="idx_retail_price"),
        ]

    def __str__(self):
        return f"{self.name} ({self.city}, {self.state}) - ${self.retail_price:.3f}/gal"
