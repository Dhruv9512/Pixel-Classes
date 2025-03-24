#!/bin/bash
set -e  # Exit immediately if a command fails

echo "Activating Conda environment..."
source /opt/conda/etc/profile.d/conda.sh
conda activate myenv

echo "Waiting for database to be ready..."
sleep 5  # Ensures the database service is up

echo "Applying database migrations..."
python manage.py migrate --noinput

echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "Starting Gunicorn..."
gunicorn Pixel.wsgi:application --bind 0.0.0.0:8000 --workers=4 &

echo "Starting Celery worker..."
exec celery -A Pixel worker --loglevel=info
