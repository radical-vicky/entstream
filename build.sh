#!/bin/bash
set -e

pip install -r requirements.txt

# This is the key step: run migrations and create tables in Supabase
python manage.py migrate --noinput

# If you have Tailwind and static files, keep the original commands
python manage.py tailwind install
python manage.py tailwind build
python manage.py collectstatic --noinput
