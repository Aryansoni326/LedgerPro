import uuid
from datetime import timedelta

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class User(AbstractUser):
    # Email is the unique identifier for LedgerPro v2
    email = models.EmailField(unique=True)
    google_sub = models.CharField(max_length=255, blank=True, null=True, unique=True)
    avatar_url = models.URLField(max_length=1024, blank=True, null=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    def save(self, *args, **kwargs):
        if not self.username:
            self.username = self.email
        super().save(*args, **kwargs)

    def __str__(self):
        return self.email


class OTPVerification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='otp_verifications', null=True, blank=True)
    email = models.EmailField(null=True, blank=True)
    purpose = models.CharField(max_length=50, default='login')
    pending_token = models.CharField(max_length=255, unique=True, default=uuid.uuid4)
    otp_hash = models.CharField(max_length=255) # SHA-256 hash of the 4-digit code
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    attempts = models.IntegerField(default=0)
    is_verified = models.BooleanField(default=False)
    is_locked = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(minutes=5)
        super().save(*args, **kwargs)

    def is_expired(self):
        return timezone.now() > self.expires_at

    def __str__(self):
        email_str = self.user.email if self.user else self.email
        return f"OTP ({self.purpose}) for {email_str} (Verified: {self.is_verified}, Locked: {self.is_locked})"


class OTPResendTracker(models.Model):
    email = models.EmailField()
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Resend at {self.timestamp} for {self.email}"


class OTPRateLimitEvent(models.Model):
    """Sliding-window counters for OTP brute-force and issuance rate limits."""

    EVENT_TYPES = [
        ('verify_attempt', 'Verify Attempt'),
        ('verify_failure', 'Verify Failure'),
        ('issue_otp', 'Issue OTP'),
        ('resend_otp', 'Resend OTP'),
    ]

    event_type = models.CharField(max_length=30, choices=EVENT_TYPES)
    ip_address = models.GenericIPAddressField(null=True, blank=True, db_index=True)
    email = models.EmailField(null=True, blank=True, db_index=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        indexes = [
            models.Index(fields=['event_type', 'ip_address', 'timestamp']),
            models.Index(fields=['event_type', 'email', 'timestamp']),
        ]

    def __str__(self):
        return f"{self.event_type} @ {self.timestamp}"
