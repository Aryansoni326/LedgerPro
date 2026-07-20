from django.urls import path

from . import views

urlpatterns = [
    path('firms', views.list_create_firms, name='list_create_firms'),
    path('firms/<int:pk>', views.firm_detail, name='firm_detail'),
    path('firms/<int:pk>/activity', views.firm_activity, name='firm_activity'),
    path('firms/<int:pk>/verify-otp', views.verify_firm_otp, name='verify_firm_otp'),
    path('firms/<int:pk>/resend-otp', views.resend_firm_otp, name='resend_firm_otp'),
]
