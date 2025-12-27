import json
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth.models import AnonymousUser

class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = self.scope.get("user")

        if not user or isinstance(user, AnonymousUser):
            await self.close()
            return

        self.group_name = f"user_{user.id}"

        # Join the user's personal notification group
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name,
        )

        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name,
        )

    # ✅ FIXED: This was missing! It actually sends the data to the frontend
    async def notify_message(self, event):
        await self.send(text_data=json.dumps({
            "type": "notification",
            "data": event["data"],
        }))