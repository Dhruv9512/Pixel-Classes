#!/bin/bash
set -e  # Exit on error

echo "Activating Conda environment..."
source /opt/conda/etc/profile.d/conda.sh
conda run --no-capture-output -n myenv python -c "print('Conda environment activated.')"

echo "Waiting for database to be ready..."
sleep 5  # Ensure the database is up before migrations

echo "Applying database migrations..."
conda run --no-capture-output -n myenv python manage.py migrate --noinput

echo "Collecting static files..."
conda run --no-capture-output -n myenv python manage.py collectstatic --noinput

echo "Starting Gunicorn..."
conda run --no-capture-output -n myenv gunicorn Pixel.wsgi:application --bind 0.0.0.0:8000 --workers=3 &

echo "Starting Celery worker..."
exec conda run --no-capture-output -n myenv celery -A Pixel worker --loglevel=info --pool=solo --max-tasks-per-child=5
