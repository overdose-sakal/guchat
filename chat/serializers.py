from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.core.cache import cache
from .models import ChatRoom, ChatMember, Message

User = get_user_model()

class UserPublicSerializer(serializers.ModelSerializer):
    display_name = serializers.ReadOnlyField()
    is_online = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ("id", "username", "display_name", "profile_picture", "is_online")

    def get_is_online(self, obj):
        return cache.get(f"user_online_{obj.id}") is not None

class MessageSerializer(serializers.ModelSerializer):
    sender = UserPublicSerializer(read_only=True)
    sender_id = serializers.IntegerField(source="sender.id", read_only=True)

    class Meta:
        model = Message
        fields = ("id", "sender", "sender_id", "content", "created_at")

class ChatRoomSerializer(serializers.ModelSerializer):
    members = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()

    class Meta:
        model = ChatRoom
        fields = ("id", "is_group", "name", "members", "last_message", "unread_count", "created_at")

    def get_members(self, obj):
        return [UserPublicSerializer(m.user).data for m in obj.members.all()]

    def get_last_message(self, obj):
        latest_msg = getattr(obj, "latest_message", None)
        if latest_msg:
            return MessageSerializer(latest_msg).data
        return None

    def get_unread_count(self, obj):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return 0

        membership = getattr(obj, "current_user_membership", None)
        latest_msg = getattr(obj, "latest_message", None)

        if membership and latest_msg:
            # ✅ STRICT FIX: Only unread if message is NEW AND sender is NOT ME
            if (
                (membership.last_read_at is None or latest_msg.created_at > membership.last_read_at)
                and latest_msg.sender_id != request.user.id
            ):
                return 1
        return 0

class ChatCreateSerializer(serializers.Serializer):
    user_ids = serializers.ListField(child=serializers.IntegerField(), allow_empty=False, min_length=2)
    is_group = serializers.BooleanField(default=False)
    name = serializers.CharField(required=False, allow_blank=True)

    def validate_user_ids(self, value):
        if len(value) != len(set(value)):
            raise serializers.ValidationError("Duplicate user IDs not allowed.")
        return value

    def validate(self, attrs):
        user_ids = attrs["user_ids"]
        is_group = attrs.get("is_group", False)
        if not is_group and len(user_ids) != 2:
            raise serializers.ValidationError("One-to-one chat must have exactly 2 users.")
        if is_group and not attrs.get("name"):
            raise serializers.ValidationError("Group chat requires a name.")
        return attrs