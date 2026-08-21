#!/usr/bin/env bash
# Prefer named-queue workers via docker-compose.yml in local/prod VMs.
# This script is a single-process fallback (Render starter / emergency only).
# WARNING: consuming all queues in one process can let agents starve extraction.
set -e
exec celery -A ledgerpro_backend worker \
  -Q extraction,risk,agents,default \
  --loglevel=info \
  --concurrency="${CELERY_CONCURRENCY:-2}" \
  --prefetch-multiplier=1
