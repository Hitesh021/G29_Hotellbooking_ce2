from django import forms
from .models import Reservation, Hotel, Flight

class ReservationForm(forms.ModelForm):
    class Meta:
        model = Reservation
        fields = ['user', 'hotel', 'flight', 'check_in', 'check_out', 'status']
        widgets = {
            'check_in': forms.DateInput(attrs={'type': 'date'}),
            'check_out': forms.DateInput(attrs={'type': 'date'}),
        }

class HotelForm(forms.ModelForm):
    class Meta:
        model = Hotel
        fields = [
            'name', 'location', 'manager', 'description',
            'hotel_id', 'address_line', 'city_name', 'country_code',
            'postal_code', 'rating', 'image_url', 'price_per_night',
            'available_rooms', 'status'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'image_url': forms.URLInput(attrs={'placeholder': 'https://example.com/image.jpg'}),
        }
        help_texts = {
            'hotel_id': 'A unique identifier for this hotel (e.g., HTL12345)',
            'image_url': 'URL to an image of the hotel',
            'rating': 'Star rating (1-5)',
        }

    def clean_hotel_id(self):
        hotel_id = self.cleaned_data.get('hotel_id')
        # Check that the hotel_id is unique (unless this is an update)
        if Hotel.objects.filter(hotel_id=hotel_id).exists() and self.instance and self.instance.hotel_id != hotel_id:
            raise forms.ValidationError("This hotel ID is already in use.")
        return hotel_id

class FlightForm(forms.ModelForm):
    class Meta:
        model = Flight
        fields = [
            'airline', 'flight_number', 'carrier_code',
            'origin', 'destination', 'origin_iata', 'destination_iata',
            'departure_time', 'arrival_time',
            'base_price', 'taxes', 'total_price', 'currency',
            'status', 'flight_id'
        ]
        widgets = {
            'departure_time': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'arrival_time': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'base_price': forms.NumberInput(attrs={'step': '0.01'}),
            'taxes': forms.NumberInput(attrs={'step': '0.01'}),
            'total_price': forms.NumberInput(attrs={'step': '0.01'}),
        }
        help_texts = {
            'flight_id': 'A unique identifier for this flight (e.g., FL12345)',
            'carrier_code': 'Airline code (e.g., AA for American Airlines)',
            'origin_iata': '3-letter IATA code for origin airport (e.g., JFK)',
            'destination_iata': '3-letter IATA code for destination airport (e.g., LAX)',
        }

    def clean_flight_id(self):
        flight_id = self.cleaned_data.get('flight_id')
        # Check that the flight_id is unique (unless this is an update)
        if Flight.objects.filter(flight_id=flight_id).exists() and self.instance and self.instance.flight_id != flight_id:
            raise forms.ValidationError("This flight ID is already in use.")
        return flight_id
        
    def clean(self):
        cleaned_data = super().clean()
        departure_time = cleaned_data.get('departure_time')
        arrival_time = cleaned_data.get('arrival_time')
        
        # Check that arrival time is after departure time
        if departure_time and arrival_time and arrival_time <= departure_time:
            raise forms.ValidationError("Arrival time must be after departure time.")
            
        # Auto-calculate total price if not provided
        base_price = cleaned_data.get('base_price')
        taxes = cleaned_data.get('taxes')
        total_price = cleaned_data.get('total_price')
        
        if base_price and taxes and not total_price:
            cleaned_data['total_price'] = base_price + taxes
            
        return cleaned_data

