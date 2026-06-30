from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('accounts.urls')),
    path('api/', include('firms.urls')),
    path('api/', include('invoices.urls')),
    path('api/', include('vault.urls')),
    path('api/', include('analytics.urls')),
    path('api/', include('trade_docs.urls')),
]



if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
