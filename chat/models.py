from django.db import models
from django.conf import settings

User = settings.AUTH_USER_MODEL


class ChatRoom(models.Model):
    is_group = models.BooleanField(default=False)
    name = models.CharField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        if self.is_group:
            return f"Group: {self.name}"
        return f"ChatRoom {self.id}"


class ChatMember(models.Model):
    chat = models.ForeignKey(
        ChatRoom,
        on_delete=models.CASCADE,
        related_name="members",
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="chat_memberships",
    )
    is_admin = models.BooleanField(default=False)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("chat", "user")

    def __str__(self):
        return f"{self.user} in chat {self.chat_id}"


class Message(models.Model):
    chat = models.ForeignKey(
        ChatRoom,
        on_delete=models.CASCADE,
        related_name="messages",
    )
    sender = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="sent_messages",
    )
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Message {self.id} from {self.sender}"
