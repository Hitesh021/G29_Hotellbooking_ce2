from django.db.models.signals import post_save
from django.contrib.auth.models import User
from django.dispatch import receiver
from loginApp.models import UserProfile

@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    # Create a new UserProfile if it doesn't exist
    if created:
        UserProfile.objects.create(user=instance)
    else:
        # If the user already exists, just save the associated UserProfile
        if hasattr(instance, 'userprofile'):
            instance.userprofile.save()
