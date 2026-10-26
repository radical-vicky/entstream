#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

# Install dependencies
pip install -r requirements.txt

# Run database migrations
python manage.py migrate --noinput

# Build Tailwind
python manage.py tailwind install
python manage.py tailwind build

# Collect static files
python manage.py collectstatic --noinput
