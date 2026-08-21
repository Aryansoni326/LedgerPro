from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.decorators.clickjacking import xframe_options_exempt
from django.views.static import serve

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('accounts.urls')),
    path('api/', include('firms.urls')),
    path('api/', include('invoices.urls')),
    path('api/', include('vault.urls')),
    path('api/', include('analytics.urls')),
    path('api/', include('trade_docs.urls')),
    path('api/', include('eway_bills.urls')),
    path('api/', include('intelligence.urls')),
    path('api/', include('agents.urls')),
    path('api/', include('billing.urls')),
]



# Serve uploaded media in all environments. Production ideally uses R2/CDN;
# local fallback still needs this route when R2 is unset (common on free Render).
urlpatterns += [
    re_path(r'^media/(?P<path>.*)$', xframe_options_exempt(serve), {'document_root': settings.MEDIA_ROOT}),
]

