#!/usr/bin/env bash
set -o errexit

echo "📦 Installing dependencies"
pip install -r requirements.txt

echo "Makemigrations"
python manage.py makemigrations

echo "🧱 Running migrations"
python manage.py migrate

echo "📂 Collecting static files"
python manage.py collectstatic --noinput

echo "👤 Creating superuser if not exists"
python manage.py shell <<EOF
from django.contrib.auth import get_user_model
import os

User = get_user_model()

username = "sakal"
email = "sakalytshit@gmail.com"
password = "Salibill1"

if username and password:
    if not User.objects.filter(username=username).exists():
        User.objects.create_superuser(
            username=username,
            email=email,
            password=password
        )
        print("✅ Superuser created")
    else:
        print("ℹ️ Superuser already exists")
else:
    print("⚠️ Superuser env vars not set")
EOF
