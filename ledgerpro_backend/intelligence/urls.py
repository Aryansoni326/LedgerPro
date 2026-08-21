from django.urls import path

from . import views

urlpatterns = [
    # Document endpoints
    path('firms/<int:firm_id>/documents/upload', views.upload_documents, name='upload_documents'),
    path('firms/<int:firm_id>/documents', views.list_documents, name='list_documents'),
    path('documents/<int:pk>', views.manage_document, name='manage_document'),
    path('documents/<int:pk>/verify', views.verify_document, name='verify_document'),
    path('documents/<int:pk>/retry-extraction', views.retry_document_extraction, name='retry_document_extraction'),

    # Risk Signal endpoints
    path('firms/<int:firm_id>/risk-signals/', views.list_risk_signals, name='list_risk_signals'),
    path('firms/<int:firm_id>/risk-summary/', views.risk_summary, name='risk_summary'),
    path('risk-signals/<int:pk>', views.manage_risk_signal, name='manage_risk_signal'),

    # Cash-flow forecast
    path('firms/<int:firm_id>/cash-flow-forecast/', views.cash_flow_forecast, name='cash_flow_forecast'),

    # Vendor / Customer scores
    path('firms/<int:firm_id>/vendor-scores/', views.vendor_score_list, name='vendor_score_list'),
    path('firms/<int:firm_id>/customer-scores/', views.customer_score_list, name='customer_score_list'),
    path('vendors/<int:pk>/score/', views.vendor_score_detail, name='vendor_score_detail'),
    path('customers/<int:pk>/score/', views.customer_score_detail, name='customer_score_detail'),

    # Trade-finance analysis
    path('firms/<int:firm_id>/trade-finance/', views.trade_finance_analysis, name='trade_finance_analysis'),

    # Graph traversal
    path('firms/<int:firm_id>/graph/risk-signal/<int:signal_id>/', views.risk_signal_graph, name='risk_signal_graph'),
    path('firms/<int:firm_id>/graph/vendor/<int:vendor_id>/', views.vendor_graph, name='vendor_graph'),
    path('firms/<int:firm_id>/graph/customer/<int:customer_id>/', views.customer_graph, name='customer_graph'),
    path('firms/<int:firm_id>/graph/evidence/', views.evidence_graph, name='evidence_graph'),
]
