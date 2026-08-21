#!/bin/sh
# Print Resend configuration status without leaking the full API key.
key="${RESEND_API_KEY:-}"
from="${DEFAULT_FROM_EMAIL:-}"
if [ -n "$key" ]; then
  echo "RESEND_CONFIGURED=yes"
  echo "RESEND_KEY_LEN=${#key}"
else
  echo "RESEND_CONFIGURED=no"
fi
echo "DEFAULT_FROM_EMAIL=${from:-(unset)}"
