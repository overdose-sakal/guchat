from django.urls import path
from chat.consumers import ChatConsumer
from chat.notification_consumers import NotificationConsumer

websocket_urlpatterns = [
    path("ws/chat/<int:chat_id>/", ChatConsumer.as_asgi()),
    path("ws/notifications/", NotificationConsumer.as_asgi()),
]

