from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

class UserProfile(models.Model):
    ROLE_CHOICES = (
        ('customer', 'Customer'),
        ('manager', 'Hotel Manager'),
        ('admin', 'Admin'),
    )

    # User is linked to the default Django User model
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    
    # Role for the user (customer, manager, or admin)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='customer')

    # Only used by hotel managers
    hotel_name = models.CharField(max_length=100, blank=True, null=True)

    # Date fields to track creation and updates
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Status of the user (active or inactive)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.user.username} - {self.get_role_display()}"

    # Role helper methods
    def is_customer(self):
        return self.role == 'customer'

    def is_manager(self):
        return self.role == 'manager'

    def is_admin(self):
        return self.role == 'admin'

    # Safe hotel display (only managers have hotel_name)
    def get_hotel(self):
        return self.hotel_name if self.is_manager() else "N/A"

    # Optional validation for hotel_name when role is 'manager'
    def clean(self):
        if self.role == 'manager' and not self.hotel_name:
            raise ValidationError("Hotel name is required for managers.")

class UserActivity(models.Model):
    ACTIVITY_TYPES = (
        ('search_hotel', 'Hotel Search'),
        ('search_flight', 'Flight Search'),
        ('view_hotel', 'View Hotel'),
        ('view_flight', 'View Flight'),
        ('add_to_cart', 'Add to Cart'),
        ('booking', 'Complete Booking'),
        ('login', 'User Login'),
    )
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='activities')
    activity_type = models.CharField(max_length=20, choices=ACTIVITY_TYPES)
    title = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']
        verbose_name_plural = 'User Activities'
    
    def __str__(self):
        return f"{self.user.username} - {self.activity_type} - {self.timestamp.strftime('%Y-%m-%d %H:%M')}"