from django.urls import path

from . import views

urlpatterns = [
    path('health', views.health, name='health'),
    path('auth/google/initiate', views.google_initiate, name='google_initiate'),
    path('auth/google/callback', views.google_callback, name='google_callback'),
    path('auth/email/login', views.email_login, name='email_login'),
    path('auth/owner/login', views.owner_login, name='owner_login'),
    path('auth/otp/verify', views.otp_verify, name='otp_verify'),
    path('auth/otp/resend', views.otp_resend, name='otp_resend'),
    path('auth/register/google', views.register_with_google, name='register_google'),
    path('auth/register/email', views.register_with_email, name='register_email'),
    path('auth/register/complete-profile', views.complete_profile, name='complete_profile'),
]
