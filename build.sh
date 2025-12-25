#!/usr/bin/env bash
set -o errexit

echo "📦 Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo "🧱 Applying database migrations..."
python manage.py migrate --noinput

echo "🎨 Collecting static files..."
python manage.py collectstatic --noinput

echo "✅ Build completed successfully"
