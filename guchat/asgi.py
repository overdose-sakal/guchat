import os
import django

# 1️⃣ Set settings module FIRST
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "guchat.settings")

# 2️⃣ Setup Django BEFORE importing anything else
django.setup()

from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter

# 3️⃣ Now it is SAFE to import Django-dependent code
from chat.middleware import JWTAuthMiddleware
import guchat.routing

application = ProtocolTypeRouter({
    "http": get_asgi_application(),
    "websocket": JWTAuthMiddleware(
        URLRouter(guchat.routing.websocket_urlpatterns)
    ),
})

