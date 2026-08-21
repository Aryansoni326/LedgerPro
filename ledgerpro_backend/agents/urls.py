from django.urls import path

from . import views

urlpatterns = [
    # Ask LedgerPro — primary conversational endpoint
    path('firms/<int:firm_id>/ask/', views.ask_ledgerpro, name='ask_ledgerpro'),

    # Agent orchestration (lower-level)
    path('firms/<int:firm_id>/agent/query/', views.agent_query, name='agent_query'),
    path('firms/<int:firm_id>/agent/history/', views.agent_history, name='agent_history'),
    path('firms/<int:firm_id>/agent/approvals/', views.list_approvals, name='agent_approvals'),
    path('agent/conversations/<uuid:pk>/', views.conversation_detail, name='agent_conversation_detail'),
    path('agent/approvals/<uuid:pk>/', views.approve_action, name='agent_approve_action'),
    path('agent/sessions/<uuid:pk>/', views.session_detail, name='agent_session_detail'),
]
