from rest_framework import serializers
from django.contrib.auth import get_user_model

from .models import ChatRoom, ChatMember, Message

User = get_user_model()


class UserPublicSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "username")


class MessageSerializer(serializers.ModelSerializer):
    sender = UserPublicSerializer(read_only=True)

    class Meta:
        model = Message
        fields = ("id", "sender", "content", "created_at")


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
        last_msg = obj.messages.last()
        if not last_msg:
            return None
        return MessageSerializer(last_msg).data


class ChatCreateSerializer(serializers.Serializer):
    user_ids = serializers.ListField(
        child=serializers.IntegerField(),
        allow_empty=False,
    )
    is_group = serializers.BooleanField(default=False)
    name = serializers.CharField(required=False, allow_blank=True)


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
