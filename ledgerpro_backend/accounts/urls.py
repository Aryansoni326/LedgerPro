from django.urls import path

from . import views

urlpatterns = [
    path('auth/google/callback', views.google_callback, name='google_callback'),
    path('auth/otp/verify', views.otp_verify, name='otp_verify'),
    path('auth/otp/resend', views.otp_resend, name='otp_resend'),
]
