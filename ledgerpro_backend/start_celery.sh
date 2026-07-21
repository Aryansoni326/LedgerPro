#!/usr/bin/env bash
set -e
exec celery -A ledgerpro_backend worker --loglevel=info --concurrency=2
