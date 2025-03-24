#!/bin/bash
set -e  # Exit on error

echo "Activating Conda environment..."
source /opt/conda/etc/profile.d/conda.sh
conda activate myenv

echo "Applying database migrations..."
python manage.py migrate --noinput

echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "Starting Gunicorn..."
gunicorn Pixel.wsgi:application --bind 0.0.0.0:8000 --workers=4 &

echo "Starting Celery worker..."
exec celery -A Pixel worker --loglevel=info
