from django.db import models
from django.conf import settings

# If you're using a CustomUser model from loginApp
User = settings.AUTH_USER_MODEL


class Hotel(models.Model):
    name = models.CharField(max_length=100)
    location = models.CharField(max_length=100)
    manager = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    # Additional fields for API compatibility
    hotel_id = models.CharField(max_length=50, unique=True)
    address_line = models.CharField(max_length=255, blank=True)
    city_name = models.CharField(max_length=100)
    country_code = models.CharField(max_length=3)
    postal_code = models.CharField(max_length=20, blank=True)
    rating = models.IntegerField(null=True, blank=True)  # Star rating 1-5
    image_url = models.URLField(max_length=500, blank=True)
    price_per_night = models.DecimalField(max_digits=10, decimal_places=2)
    available_rooms = models.IntegerField(default=0)
    # Status (to match the UI)
    STATUS_CHOICES = (
        ('active', 'Active'),
        ('pending', 'Pending'),
        ('inactive', 'Inactive'),
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='active')

    def __str__(self):
        return self.name


class Flight(models.Model):
    airline = models.CharField(max_length=100)
    flight_number = models.CharField(max_length=50)
    origin = models.CharField(max_length=100)
    destination = models.CharField(max_length=100)
    departure_time = models.DateTimeField()
    arrival_time = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    # Additional fields for API compatibility
    flight_id = models.CharField(max_length=50, unique=True)
    carrier_code = models.CharField(max_length=10)
    origin_iata = models.CharField(max_length=3)
    destination_iata = models.CharField(max_length=3)
    # Price information
    base_price = models.DecimalField(max_digits=10, decimal_places=2)
    taxes = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='USD')
    # Status
    STATUS_CHOICES = (
        ('scheduled', 'Scheduled'),
        ('delayed', 'Delayed'),
        ('cancelled', 'Cancelled'),
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='scheduled')

    def __str__(self):
        return f"{self.airline} ({self.flight_number})"


class Reservation(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    hotel = models.ForeignKey(Hotel, on_delete=models.SET_NULL, null=True, blank=True)
    flight = models.ForeignKey(Flight, on_delete=models.SET_NULL, null=True, blank=True)
    check_in = models.DateField(null=True, blank=True)
    check_out = models.DateField(null=True, blank=True)
    booking_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=(
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
    ), default='pending')

    def __str__(self):
        return f"Reservation by {self.user} - Status: {self.status}"


class SupportRequest(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    request_type = models.CharField(max_length=100)
    message = models.TextField()
    status = models.CharField(max_length=20, choices=(
        ('open', 'Open'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
    ), default='open')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user} - {self.request_type}"
