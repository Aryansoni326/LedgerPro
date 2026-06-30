from django.urls import path

from . import views

urlpatterns = [
    path('firms/<int:firm_id>/invoices/upload', views.upload_invoices, name='upload_invoices'),
    path('firms/<int:firm_id>/invoices', views.list_invoices, name='list_invoices'),
    path('invoices/<int:pk>', views.manage_invoice, name='manage_invoice'),
    path('invoices/<int:pk>/verify', views.verify_invoice, name='verify_invoice'),
    path('invoices/<int:pk>/retry-extraction', views.retry_extraction, name='retry_extraction'),
    path('firms/<int:firm_id>/invoices/export-excel', views.export_excel, name='export_excel'),
]
