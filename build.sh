#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

echo "--- INSTALLING DEPENDENCIES ---"
python -m pip install -r requirements.txt

echo "--- RUNNING MIGRATIONS ---"
python manage.py migrate --noinput

echo "--- COLLECTING STATIC FILES ---"
python manage.py collectstatic --noinput

echo "--- BUILD COMPLETE ---"