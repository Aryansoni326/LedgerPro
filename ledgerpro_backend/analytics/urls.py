from django.urls import path

from . import views

urlpatterns = [
    path('firms/<int:firm_id>/analytics/turnover', views.analytics_turnover, name='analytics_turnover'),
    path('firms/<int:firm_id>/analytics/summary', views.analytics_summary, name='analytics_summary'),
]
