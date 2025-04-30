from django.urls import path, include
from . import views

urlpatterns = [
    # --- Authentication Routes ---
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('logout/', views.logout_view, name='logout'),

    # --- CSRF Failure Handler ---
    path('csrf-failure/', views.csrf_failure, name='csrf_failure'),

    # --- AdminApp URLs (for dashboards, users, etc.) ---
    path('adminApp/', include(('adminApp.urls', 'adminApp'), namespace='adminApp')),

   # Ensure you have the home route here to handle customer redirection
   # You should have a home view and URL defined in your main app or root URLs
   path('', include('app1.urls')),  # or whatever the name of the app handling the homepage is
   
]
