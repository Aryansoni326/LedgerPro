from django.urls import path

from . import views

urlpatterns = [
    path('firms/<int:firm_id>/eway-bills/upload', views.upload_eway_bills, name='upload_eway_bills'),
    path('firms/<int:firm_id>/eway-bills', views.list_eway_bills, name='list_eway_bills'),
    path('eway-bills/<int:pk>', views.update_eway_bill, name='update_eway_bill'),
    path('eway-bills/<int:pk>/delete', views.delete_eway_bill, name='delete_eway_bill_compat'),  # support direct action
    path('eway-bills/<int:pk>/verify', views.verify_eway_bill, name='verify_eway_bill'),
    path('eway-bills/<int:pk>/retry-extraction', views.retry_eway_bill_extraction, name='retry_eway_bill_extraction'),
]
