#!/bin/bash
set -e
echo "--- INSTALLING DEPENDENCIES ---"
python -m pip install -r requirements.txt
echo "--- COLLECTING STATIC FILES ---"
python manage.py collectstatic --noinput
echo "--- BUILD COMPLETE ---"
