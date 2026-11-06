#!/bin/sh
set -eu
cd /app
/app/.venv/bin/python -m media_manager.onboarding
exec /app/mediamanager-startup.sh
