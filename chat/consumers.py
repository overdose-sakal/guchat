HEARTBEAT_INTERVAL = 30  # seconds


import json

from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth.models import AnonymousUser
from channels.db import database_sync_to_async

from .models import ChatMember, Message


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = self.scope.get("user")

        # Reject unauthenticated users
        if not user or isinstance(user, AnonymousUser):
            await self.close()
            return

        self.user = user
        self.chat_id = self.scope["url_route"]["kwargs"]["chat_id"]
        self.room_group_name = f"chat_{self.chat_id}"

        # Check membership
        if not await self.is_chat_member(user, self.chat_id):
            await self.close()
            return

        # Join chat room
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name,
        )

        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "room_group_name"):
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name,
            )


    async def receive(self, text_data=None, bytes_data=None):
        if not text_data:
            return

        try:
            data = json.loads(text_data)
        except json.JSONDecodeError:
            return

        # ❤️ Heartbeat ping
        if data.get("type") == "ping":
            await self.send(text_data=json.dumps({"type": "pong"}))
            return

        content = data.get("content")

        if not isinstance(content, str) or not content.strip():
            return

        message = await self.create_message(
            chat_id=self.chat_id,
            user=self.user,
            content=content.strip(),
        )

        member_ids = await self.get_chat_members(self.chat_id)

        for user_id in member_ids:
            await self.channel_layer.group_send(
                f"user_{user_id}",
                {
                    "type": "notify.message",
                    "data": {
                        "chat_id": self.chat_id,
                        "sender": self.user.username,
                        "content": message.content,
                        "created_at": message.created_at.isoformat(),
                    },
                },
            )

        await self.channel_layer.group_send(
            self.room_group_name,
            {
                "type": "chat.message",
                "message": {
                    "id": message.id,
                    "content": message.content,
                    "sender": self.user.username,
                    "created_at": message.created_at.isoformat(),
                },
            },
        )


    async def chat_message(self, event):
        await self.send(text_data=json.dumps(event["message"]))

    async def notify_message(self, event):
        await self.send(text_data=json.dumps({
            "type": "notification",
            "data": event["data"],
        }))

    # --------------------
    # Database helpers
    # --------------------

    @database_sync_to_async
    def is_chat_member(self, user, chat_id):
        return ChatMember.objects.filter(chat_id=chat_id, user=user).exists()

    @database_sync_to_async
    def get_chat_members(self, chat_id):
        return list(
            ChatMember.objects
            .filter(chat_id=chat_id)
            .values_list("user_id", flat=True)
        )

    @database_sync_to_async
    def create_message(self, chat_id, user, content):
        return Message.objects.create(
            chat_id=chat_id,
            sender=user,
            content=content,
        )

# chat/consumers.py
from channels.generic.websocket import AsyncWebsocketConsumer
from django.contrib.auth.models import AnonymousUser
from django.core.cache import cache # ✅ Import cache

class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = self.scope.get("user")
        if not user or isinstance(user, AnonymousUser):
            await self.close()
            return

        self.group_name = f"user_{user.id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        # ✅ Mark user as ONLINE in Redis (lasts 5 minutes, refreshes on activity)
        # We set it for a long time, but delete on disconnect
        await cache.set(f"user_online_{user.id}", True, timeout=None)

    async def disconnect(self, close_code):
        user = self.scope.get("user")
        if user:
            # ✅ Mark user as OFFLINE
            await cache.delete(f"user_online_{user.id}")
            
        await self.channel_layer.group_discard(self.group_name, self.channel_name)