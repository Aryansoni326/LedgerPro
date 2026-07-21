import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ledgerpro_backend.settings')

application = get_wsgi_application()
# Vercel Python runtime also looks for `app`
app = application
