from django.urls import path

from . import views

urlpatterns = [
    path('firms/<int:firm_id>/trade-docs/upload', views.upload_trade_docs, name='upload_trade_docs'),
    path('firms/<int:firm_id>/trade-docs', views.list_trade_docs, name='list_trade_docs'),
    path('trade-docs/<int:pk>', views.manage_trade_doc, name='manage_trade_doc'),
    path('trade-docs/<int:pk>/verify', views.verify_trade_doc, name='verify_trade_doc'),
    path('trade-docs/<int:pk>/retry-extraction', views.retry_trade_doc_extraction, name='retry_trade_doc_extraction'),
]
