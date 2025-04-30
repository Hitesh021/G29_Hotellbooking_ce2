from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse
from django.contrib.auth.models import User
from django.contrib.sessions.models import Session
from django.utils import timezone
from django.db.models import Q
from loginApp.models import UserProfile
from .models import Reservation, Hotel, Flight
from .forms import ReservationForm, HotelForm, FlightForm


# ------------------------- ADMIN DASHBOARD -------------------------
@login_required(login_url='/')
def admin_dashboard(request):
    if not request.user.is_superuser:
        messages.error(request, "Access denied. You are not an admin.")
        return redirect(reverse('login'))

    profile, _ = UserProfile.objects.get_or_create(user=request.user, defaults={'role': 'admin'})

    total_hotels = Hotel.objects.count()
    total_reservations = Reservation.objects.count()
    total_users = UserProfile.objects.filter(role='customer').count()

    return render(request, 'adminApp/dashboards/admin_dashboard.html', {
        'role': profile.role,
        'total_hotels': total_hotels,
        'total_reservations': total_reservations,
        'total_users': total_users,
    })


# ------------------------- MANAGER DASHBOARD -------------------------
@login_required(login_url='/')
def manager_dashboard(request):
    try:
        profile = request.user.userprofile
        if profile.role != 'manager':
            raise PermissionError
    except (UserProfile.DoesNotExist, PermissionError):
        messages.error(request, "Unauthorized access. You are not a manager.")
        return redirect(reverse('login'))

    return render(request, 'adminApp/dashboards/manager_dashboard.html', {
        'role': profile.role,
        'hotel_name': profile.hotel_name or "Not Assigned"
    })


# ------------------------- CUSTOMER DASHBOARD -------------------------
@login_required(login_url='/')
def customer_dashboard(request):
    try:
        profile = request.user.userprofile
        if profile.role != 'customer':
            raise PermissionError
    except (UserProfile.DoesNotExist, PermissionError):
        messages.error(request, "Unauthorized access. You are not a customer.")
        return redirect(reverse('login'))

    return render(request, 'adminApp/dashboards/customer_dashboard.html', {
        'role': profile.role,
        'customer_name': request.user.username
    })


# ------------------------- ADMIN: RESERVATIONS VIEW -------------------------
@login_required(login_url='/')
def reservations_view(request):
    if not request.user.is_superuser:
        messages.error(request, "Access denied. You are not an admin.")
        return redirect(reverse('login'))

    reservations = Reservation.objects.all().order_by('-booking_date')
    return render(request, 'adminApp/dashboards/reservations.html', {
        'reservations': reservations,
    })

@login_required(login_url='/')
def reservations(request):
    reservations = Reservation.objects.all()
    return render(request, 'adminApp/reservations.html', {'reservations': reservations})

def reservation_detail(request, booking_id):
    # Retrieve the reservation using the booking_id
    reservation = get_object_or_404(Reservation, id=booking_id)

    # Pass the reservation object to the template
    return render(request, 'adminApp/reservation_details.html', {
        'reservation': reservation,
    })

def create_reservation(request):
    if request.method == 'POST':
        form = ReservationForm(request.POST)
        if form.is_valid():
            # Save the reservation to the database
            form.save()
            # Redirect to the reservations page after saving
            return redirect('adminApp:reservations')
    else:
        form = ReservationForm()

    return render(request, 'adminApp/create_reservation.html', {'form': form})

# View to display all reservations in a table
def reservations(request):
    reservations_list = Reservation.objects.all()  # Get all reservations
    return render(request, 'adminApp/reservations.html', {'reservations': reservations_list})

# ------------------------- ADMIN: USERS TABLE (with search + filter) -------------------------
@login_required(login_url='/')
def user_list_view(request):
    if not request.user.is_superuser:
        messages.error(request, "Access denied. You are not an admin.")
        return redirect(reverse('login'))

    # Search and role filter
    search_query = request.GET.get('search', '')
    role_filter = request.GET.get('role', '')

    # Base queryset
    registered_users = UserProfile.objects.select_related('user').all()

    # Apply search
    if search_query:
        registered_users = registered_users.filter(
            Q(user__username__icontains=search_query) |
            Q(user__email__icontains=search_query)
        )

    # Apply role filter
    if role_filter:
        registered_users = registered_users.filter(role=role_filter)

    # Get active users from session
    sessions = Session.objects.filter(expire_date__gte=timezone.now())
    active_user_ids = [
        int(session.get_decoded().get('_auth_user_id'))
        for session in sessions
        if session.get_decoded().get('_auth_user_id') is not None
    ]
    active_users = registered_users.filter(user__id__in=active_user_ids)

    context = {
        'registered_users': registered_users,
        'active_users': active_users,
        'search_query': search_query,
        'role_filter': role_filter,
    }

    return render(request, 'adminApp/dashboards/users.html', context)


# ------------------------- ADMIN: SINGLE USER DETAIL -------------------------
@login_required(login_url='/')
def user_detail_view(request, user_id):
    if not request.user.is_superuser:
        messages.error(request, "Access denied. You are not an admin.")
        return redirect('adminApp:user_list_view')

    user_profile = get_object_or_404(UserProfile, user__id=user_id)

    return render(request, 'adminApp/dashboards/user_detail.html', {
        'profile': user_profile
    })


# ------------------------- ADMIN: HOTELS & FLIGHTS VIEW -------------------------
@login_required(login_url='/')
def HNF_view(request):
    if not request.user.is_superuser:
        messages.error(request, "Access denied. You are not an admin.")
        return redirect(reverse('login'))
        
    hotels = Hotel.objects.all().order_by('name')
    flights = Flight.objects.all().order_by('departure_time')
    
    return render(request, 'adminApp/dashboards/hotelsNflights.html', {
        'hotels': hotels,
        'flights': flights
    })

# ------------------------- HOTEL CRUD OPERATIONS -------------------------
@login_required(login_url='/')
def hotel_list(request):
    if not request.user.is_superuser:
        messages.error(request, "Access denied. You are not an admin.")
        return redirect(reverse('login'))
        
    hotels = Hotel.objects.all().order_by('name')
    return render(request, 'adminApp/dashboards/hotel_list.html', {'hotels': hotels})

@login_required(login_url='/')
def hotel_create(request):
    if not request.user.is_superuser:
        messages.error(request, "Access denied. You are not an admin.")
        return redirect(reverse('login'))
        
    if request.method == 'POST':
        form = HotelForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Hotel successfully created.")
            return redirect('adminApp:HNF')
    else:
        form = HotelForm()
        
    return render(request, 'adminApp/dashboards/hotel_form.html', {
        'form': form,
        'title': 'Add New Hotel'
    })

@login_required(login_url='/')
def hotel_edit(request, hotel_id):
    if not request.user.is_superuser:
        messages.error(request, "Access denied. You are not an admin.")
        return redirect(reverse('login'))
        
    hotel = get_object_or_404(Hotel, id=hotel_id)
    
    if request.method == 'POST':
        form = HotelForm(request.POST, instance=hotel)
        if form.is_valid():
            form.save()
            messages.success(request, "Hotel successfully updated.")
            return redirect('adminApp:HNF')
    else:
        form = HotelForm(instance=hotel)
        
    return render(request, 'adminApp/dashboards/hotel_form.html', {
        'form': form,
        'hotel': hotel,
        'title': 'Edit Hotel'
    })

@login_required(login_url='/')
def hotel_delete(request, hotel_id):
    if not request.user.is_superuser:
        messages.error(request, "Access denied. You are not an admin.")
        return redirect(reverse('login'))
        
    hotel = get_object_or_404(Hotel, id=hotel_id)
    
    if request.method == 'POST':
        hotel.delete()
        messages.success(request, "Hotel successfully deleted.")
        return redirect('adminApp:HNF')
        
    return render(request, 'adminApp/dashboards/hotel_confirm_delete.html', {
        'hotel': hotel
    })

# ------------------------- FLIGHT CRUD OPERATIONS -------------------------
@login_required(login_url='/')
def flight_list(request):
    if not request.user.is_superuser:
        messages.error(request, "Access denied. You are not an admin.")
        return redirect(reverse('login'))
        
    flights = Flight.objects.all().order_by('departure_time')
    return render(request, 'adminApp/dashboards/flight_list.html', {'flights': flights})

@login_required(login_url='/')
def flight_create(request):
    if not request.user.is_superuser:
        messages.error(request, "Access denied. You are not an admin.")
        return redirect(reverse('login'))
        
    if request.method == 'POST':
        form = FlightForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Flight successfully created.")
            return redirect('adminApp:HNF')
    else:
        form = FlightForm()
        
    return render(request, 'adminApp/dashboards/flight_form.html', {
        'form': form,
        'title': 'Add New Flight'
    })

@login_required(login_url='/')
def flight_edit(request, flight_id):
    if not request.user.is_superuser:
        messages.error(request, "Access denied. You are not an admin.")
        return redirect(reverse('login'))
        
    flight = get_object_or_404(Flight, id=flight_id)
    
    if request.method == 'POST':
        form = FlightForm(request.POST, instance=flight)
        if form.is_valid():
            form.save()
            messages.success(request, "Flight successfully updated.")
            return redirect('adminApp:HNF')
    else:
        form = FlightForm(instance=flight)
        
    return render(request, 'adminApp/dashboards/flight_form.html', {
        'form': form,
        'flight': flight,
        'title': 'Edit Flight'
    })

@login_required(login_url='/')
def flight_delete(request, flight_id):
    if not request.user.is_superuser:
        messages.error(request, "Access denied. You are not an admin.")
        return redirect(reverse('login'))
        
    flight = get_object_or_404(Flight, id=flight_id)
    
    if request.method == 'POST':
        flight.delete()
        messages.success(request, "Flight successfully deleted.")
        return redirect('adminApp:HNF')
        
    return render(request, 'adminApp/dashboards/flight_confirm_delete.html', {
        'flight': flight
    })