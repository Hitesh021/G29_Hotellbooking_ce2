from django.db import models
from django.contrib.auth.models import User

class CartItem(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    hotel_name = models.CharField(max_length=255)
    hotel_id = models.CharField(max_length=100, blank=True, null=True)  # Store actual hotel ID
    offer_id = models.CharField(max_length=100)  # Unique ID from Amadeus
    check_in = models.DateField()
    check_out = models.DateField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    adults = models.IntegerField(default=1)
    room_description = models.TextField(blank=True, null=True)

    added_on = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.hotel_name} ({self.check_in} to {self.check_out})"

class FlightCartItem(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    offer_id = models.CharField(max_length=100)  # Unique ID from Amadeus
    origin = models.CharField(max_length=100)
    destination = models.CharField(max_length=100)
    departure_date = models.DateTimeField()
    return_date = models.DateTimeField(null=True, blank=True)  # For one-way flights
    airline = models.CharField(max_length=100, blank=True, null=True)
    flight_number = models.CharField(max_length=50, blank=True, null=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    passengers = models.IntegerField(default=1)
    flight_class = models.CharField(max_length=50, default='ECONOMY')
    is_round_trip = models.BooleanField(default=True)
    
    added_on = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.origin} to {self.destination} ({self.departure_date.strftime('%Y-%m-%d')})"
