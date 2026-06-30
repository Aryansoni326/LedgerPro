from django.urls import path

from . import views

urlpatterns = [
    path('firms/<int:firm_id>/vault/years', views.get_vault_years, name='vault_years'),
    path('firms/<int:firm_id>/vault/<int:year>/months', views.get_vault_months, name='vault_months'),
    path('firms/<int:firm_id>/vault/<int:year>/<int:month>/days', views.get_vault_days, name='vault_days'),
    path('firms/<int:firm_id>/vault/<int:year>/<int:month>/<int:day>', views.get_vault_day_files, name='vault_day_files'),
    path('vault/<int:pk>', views.delete_vault_entry, name='delete_vault_entry'),
    path('firms/<int:firm_id>/vault/upload-stub', views.upload_stub_file, name='upload_stub_file'),
]
