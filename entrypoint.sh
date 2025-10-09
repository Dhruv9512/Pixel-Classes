#!/bin/bash
set -e  # Exit immediately if a command exits with a non-zero status

# ✅ Wait for the database to become available
echo "Waiting for database to be ready..."
# Use the correct manage.py path if your project structure is different
while ! python manage.py showmigrations &>/dev/null; do
    echo "Database not ready, waiting..."
    sleep 2
done
echo "Database is ready."

# ✅ Apply database migrations
echo "Applying database migrations..."
python manage.py migrate --noinput

# ✅ Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput

# ✅ Start Celery Worker in the background
echo "Starting Celery worker..."
celery -A Pixel worker \
  --loglevel=info \
  --pool=solo \
  --max-tasks-per-child=5 \
  --max-memory-per-child=100000 &

# ✅ Start Daphne (ASGI Server) in the foreground
echo "Starting Daphne (ASGI - WebSocket + HTTP)..."
exec daphne -b 0.0.0.0 -p 8000 Pixel.asgi:application