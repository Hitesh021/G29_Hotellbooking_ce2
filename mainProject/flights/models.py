from django.db import models
from django.contrib.auth.models import User

# Create your models here.

class FlightBooking(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='flight_bookings')
    flight_offer_id = models.CharField(max_length=100)  # Store Amadeus flight offer ID
    booking_reference = models.CharField(max_length=20, null=True, blank=True)  # PNR or booking reference
    origin = models.CharField(max_length=100)
    destination = models.CharField(max_length=100)
    departure_date = models.DateTimeField()
    return_date = models.DateTimeField(null=True, blank=True)  # For one-way flights
    passenger_count = models.IntegerField(default=1)
    booking_date = models.DateTimeField(auto_now_add=True)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='USD')
    payment_status = models.CharField(
        max_length=20,
        choices=[
            ('PENDING', 'Pending'),
            ('CONFIRMED', 'Confirmed'),
            ('CANCELLED', 'Cancelled'),
            ('REFUNDED', 'Refunded')
        ],
        default='PENDING'
    )
    is_round_trip = models.BooleanField(default=True)
    booking_details = models.JSONField(null=True, blank=True)  # Store complete booking details

    def __str__(self):
        return f"{self.origin} to {self.destination} - {self.departure_date.strftime('%Y-%m-%d')}"
