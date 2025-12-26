from rest_framework import serializers
from django.contrib.auth import get_user_model

from .models import ChatRoom, ChatMember, Message

User = get_user_model()


# --------------------------------------------------
# Minimal / Public User Serializer (with profile pic)
# --------------------------------------------------
class UserPublicSerializer(serializers.ModelSerializer):
    display_name = serializers.ReadOnlyField()

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "display_name",
            "profile_picture",
        )


# --------------------------------------------------
# Message Serializer
# --------------------------------------------------
class MessageSerializer(serializers.ModelSerializer):
    sender = UserPublicSerializer(read_only=True)
    sender_id = serializers.IntegerField(source="sender.id", read_only=True)

    class Meta:
        model = Message
        fields = (
            "id",
            "sender",
            "sender_id",
            "content",
            "created_at",
        )


# --------------------------------------------------
# ChatRoom Serializer
# --------------------------------------------------
class ChatRoomSerializer(serializers.ModelSerializer):
    members = serializers.SerializerMethodField()
    last_message = serializers.SerializerMethodField()

    class Meta:
        model = ChatRoom
        fields = (
            "id",
            "is_group",
            "name",
            "members",
            "last_message",
            "created_at",
        )

    def get_members(self, obj):
        users = User.objects.filter(chat_memberships__chat=obj)
        return UserPublicSerializer(users, many=True).data

    def get_last_message(self, obj):
        last_msg = obj.messages.order_by("-created_at").first()
        if not last_msg:
            return None
        return MessageSerializer(last_msg).data


# --------------------------------------------------
# Chat Creation Serializer
# --------------------------------------------------
class ChatCreateSerializer(serializers.Serializer):
    user_ids = serializers.ListField(
        child=serializers.IntegerField(),
        allow_empty=False,
        min_length=2,
    )
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
            raise serializers.ValidationError(
                "One-to-one chat must have exactly 2 users."
            )

        if is_group and not attrs.get("name"):
            raise serializers.ValidationError(
                "Group chat requires a name."
            )

        return attrs
