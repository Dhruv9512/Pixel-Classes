#!/bin/bash
set -e  # Exit on error

echo "Activating Conda environment..."
conda run --no-capture-output -n myenv python -c "print('Conda environment activated.')"

echo "Waiting for database to be ready..."
while ! conda run --no-capture-output -n myenv python manage.py showmigrations &>/dev/null; do
    echo "Database not ready, waiting..."
    sleep 2
done
echo "Database is ready."

echo "Applying database migrations..."
conda run --no-capture-output -n myenv python manage.py migrate --noinput

echo "Collecting static files..."
conda run --no-capture-output -n myenv python manage.py collectstatic --noinput

echo "Starting Gunicorn..."
conda run --no-capture-output -n myenv gunicorn Pixel.wsgi:application --bind 0.0.0.0:8000 --workers=3 &


echo "Starting Daphne (ASGI - WebSocket/HTTP)..."
conda run --no-capture-output -n myenv daphne -b 0.0.0.0 -p 8001 Pixel.asgi:application &


echo "Starting Celery worker..."
exec conda run --no-capture-output -n myenv celery -A Pixel worker --loglevel=info --pool=solo --max-tasks-per-child=5 --max-memory-per-child=100000
