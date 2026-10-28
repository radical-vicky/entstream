#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

echo "--- INSTALLING DEPENDENCIES ---"
python -m pip install -r requirements.txt

echo "--- COLLECTING STATIC FILES ---"
# Force Django to collect static files into the exact folder Vercel expects
python manage.py collectstatic --noinput

# Ensure the directory exists (Vercel might strip it if empty)
mkdir -p staticfiles_build/static
echo "--- BUILD COMPLETE ---"
