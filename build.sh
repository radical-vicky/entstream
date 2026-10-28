#!/bin/bash

# Exit immediately if a command fails
set -e

echo "========================================="
echo "1. Installing Python dependencies..."
echo "========================================="
pip install -r requirements.txt

echo "========================================="
echo "2. Running database migrations..."
echo "========================================="
# This will create all the tables in your Supabase database
python manage.py migrate --noinput

echo "========================================="
echo "3. Building Tailwind CSS..."
echo "========================================="
# We use `|| true` so that if Tailwind fails on Vercel, 
# the build doesn't crash completely.
python manage.py tailwind install || true
python manage.py tailwind build || true

echo "========================================="
echo "4. Collecting static files..."
echo "========================================="
python manage.py collectstatic --noinput

echo "========================================="
echo "BUILD COMPLETE!"
echo "========================================="
