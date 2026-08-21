from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

from billing.entitlements import get_or_create_subscription

User = get_user_model()


@receiver(post_save, sender=User)
def ensure_free_subscription(sender, instance, created, **kwargs):
    if created:
        get_or_create_subscription(instance)
