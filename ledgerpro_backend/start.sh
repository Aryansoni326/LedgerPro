#!/usr/bin/env bash
set -e
python manage.py migrate --noinput
python manage.py collectstatic --noinput
exec gunicorn ledgerpro_backend.wsgi:application --bind "0.0.0.0:${PORT:-8000}" --workers 2 --timeout 120
