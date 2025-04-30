# loginApp/apps.py
from django.apps import AppConfig

class LoginappConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'loginApp'

    def ready(self):
        import loginApp.signals  # Ensure signals are connected
