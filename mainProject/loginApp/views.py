from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib import messages
from django.views.decorators.csrf import csrf_protect
from django.urls import reverse
from loginApp.models import UserProfile
from django.contrib.auth import logout

# -------------------- LOGIN VIEW --------------------
@csrf_protect
def login_view(request):
    if request.method == "POST":
        username = request.POST.get('username')
        password = request.POST.get('password')
        selected_role = request.POST.get('role', '').strip().lower()
        hotel_name_input = request.POST.get('hotel_name', '').strip()

        user = authenticate(request, username=username, password=password)

        if user:
            profile, created = UserProfile.objects.get_or_create(user=user)

            if created and user.is_superuser:
                profile.role = 'admin'
                profile.save()

            actual_role = (profile.role or '').strip().lower()

            if not actual_role:
                messages.error(request, "You're a pre-registered user without a role. Please contact admin.")
                return redirect(reverse('login'))

            if actual_role != selected_role:
                messages.error(request, f"You are not assigned the role '{selected_role}'.")
                return redirect(reverse('login'))

            if selected_role == 'admin' and not user.is_superuser:
                messages.error(request, "Access denied. You are not an admin.")
                return redirect(reverse('login'))

            if selected_role == 'manager':
                if not hotel_name_input:
                    messages.error(request, "Hotel name is required for manager login.")
                    return redirect(reverse('login'))
                if not profile.hotel_name or profile.hotel_name.strip().lower() != hotel_name_input.lower():
                    messages.error(request, f"No hotel named '{hotel_name_input}' associated with this manager.")
                    return redirect(reverse('login'))

            login(request, user)
            request.session.set_expiry(0)  # session ends when browser closes
            request.session['role'] = actual_role

            if actual_role == 'admin':
                return redirect(reverse('adminApp:admin_dashboard'))
            elif actual_role == 'manager':
                return redirect(reverse('adminApp:manager_dashboard'))
            elif actual_role == 'customer':
                return redirect(reverse('home'))  # Redirect to home for customers
            else:
                messages.error(request, "Invalid role assigned.")
                return redirect(reverse('login'))

        else:
            messages.error(request, 'Invalid username or password')

    return render(request, 'loginApp/login.html')


# -------------------- REGISTER VIEW --------------------
@csrf_protect
def register_view(request):
    if request.method == "POST":
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password', '').strip()
        confirm_password = request.POST.get('confirm_password', '').strip()
        selected_role = request.POST.get('role', '').strip().lower()
        hotel_name_input = request.POST.get('hotel_name', '').strip()

        if password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return redirect(reverse('register'))

        if selected_role not in ['customer', 'manager']:
            messages.error(request, "Invalid role selected. Only 'customer' or 'manager' allowed.")
            return redirect(reverse('register'))

        if get_user_model().objects.filter(username=username).exists():
            messages.error(request, "Username already exists. Please choose a different one.")
            return redirect(reverse('register'))

        if selected_role == 'manager' and not hotel_name_input:
            messages.error(request, "Hotel name is required for managers.")
            return redirect(reverse('register'))

        user = get_user_model().objects.create_user(username=username, password=password)

        # Check if the UserProfile already exists for this user
        profile, created = UserProfile.objects.get_or_create(user=user)
        if created:
            # If the profile is newly created, assign role and hotel name if manager
            if selected_role == 'manager':
                profile.role = 'manager'
                profile.hotel_name = hotel_name_input
            else:
                profile.role = 'customer'

            profile.save()

        messages.success(request, "Registration successful! Please log in.")
        return redirect(reverse('login'))

    return render(request, 'loginApp/register.html')


# -------------------- LOGOUT VIEW --------------------

def logout_view(request):
    # Log the user out
    logout(request)
    
    # Redirect to the home page after logout
    return redirect('home')  # Replace 'home' with the name of your home page URL pattern if it's different



# -------------------- CSRF FAILURE VIEW --------------------
def csrf_failure(request, reason=""):
    return render(request, 'loginApp/errors/403.html', status=403)
