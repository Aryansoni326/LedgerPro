import os

from celery import Celery

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ledgerpro_backend.settings')

app = Celery('ledgerpro_backend')

# Use a string here so the worker doesn't have to serialize
# the configuration object to child processes.
# Namespace='CELERY' means all celery-related configuration keys
# should have a `CELERY_` prefix in Django settings.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django apps.
app.autodiscover_tasks()

@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
