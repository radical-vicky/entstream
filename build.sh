#!/bin/bash
set -e

echo "Installing dependencies..."
pip install -r requirements.txt

echo "Generating migrations for all apps..."
# This forces Django to create migration files for any app that is missing them
python manage.py makemigrations accounts videos creators payments subscriptions streaming

echo "Running database migrations..."
# --fake-initial handles tables that already exist
python manage.py migrate --noinput --fake-initial

echo "Building Tailwind..."
python manage.py tailwind install || true
python manage.py tailwind build || true

echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "Build complete!"
