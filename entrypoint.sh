#!/bin/bash
set -e

# ✅ Wait for the database, but show errors this time
echo "Waiting for database to be ready..."
while ! python manage.py showmigrations; do
    echo "Database not ready, waiting..."
    sleep 2
done
echo "Database is ready."

# (The rest of your script remains the same)

echo "Applying database migrations..."
python manage.py migrate --noinput

echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "Starting Celery worker..."
celery -A Pixel worker \
  --loglevel=info \
  --pool=solo \
  --max-tasks-per-child=5 \
  --max-memory-per-child=100000 &

echo "Starting Daphne (ASGI - WebSocket + HTTP)..."
exec daphne -b 0.0.0.0 -p 8000 Pixel.asgi:application