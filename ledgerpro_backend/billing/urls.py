from django.urls import path

from billing import views

urlpatterns = [
    path("billing/subscription/", views.my_subscription, name="billing-subscription"),
    path("billing/tiers/", views.tier_catalog, name="billing-tiers"),
    path(
        "billing/admin/users/<int:user_id>/subscription/",
        views.admin_update_subscription,
        name="billing-admin-subscription",
    ),
    path("external/v1/me/", views.external_api_bootstrap, name="external-api-me"),
]
