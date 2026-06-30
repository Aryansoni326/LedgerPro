from django.conf import settings
from django.core.validators import EmailValidator, RegexValidator
from django.db import models

# Regular expression validator for standard 15-character Indian GSTIN
gstin_regex_validator = RegexValidator(
    regex=r'^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$',
    message="Invalid GSTIN format. Must be a valid 15-character Indian GSTIN (e.g., 27AAAAA1111A1Z1)."
)

class Firm(models.Model):
    STATUS_CHOICES = [
        ('pending_verification', 'Pending Verification'),
        ('active', 'Active')
    ]

    name = models.CharField(max_length=255)
    gstin = models.CharField(max_length=15, blank=True, null=True, validators=[gstin_regex_validator])
    state = models.CharField(max_length=100)
    city = models.CharField(max_length=100)
    owner_email = models.EmailField(validators=[EmailValidator()])
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='pending_verification')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='created_firms'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.get_status_display()})"
