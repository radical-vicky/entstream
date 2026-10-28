#!/bin/bash
set -e

echo "Installing dependencies..."
pip install -r requirements.txt

echo "Generating migrations..."
# This tells Django to look at models.py and write the migration files
python manage.py makemigrations accounts
python manage.py makemigrations videos
# (Add any other apps here if they are missing migrations, like creators, etc.)

echo "Running database migrations..."
python manage.py migrate --noinput --fake-initial

echo "Building Tailwind..."
python manage.py tailwind install || true
python manage.py tailwind build || true

echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "Build complete!"
