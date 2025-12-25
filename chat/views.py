from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.db.models import Max

from .models import ChatRoom, ChatMember, Message
from .serializers import (
    ChatRoomSerializer,
    MessageSerializer,
    ChatCreateSerializer,
)


class RecentChatsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # 1. Get IDs of chats the user belongs to (avoids duplicate join rows)
        member_chat_ids = ChatMember.objects.filter(user=request.user).values_list('chat_id', flat=True)

        # 2. Fetch those chats, annotate with last message time, and sort
        chats = (
            ChatRoom.objects
            .filter(id__in=member_chat_ids)
            .annotate(last_msg_time=Max("messages__created_at"))
            .order_by("-last_msg_time", "-created_at")
        )

        serializer = ChatRoomSerializer(chats, many=True)
        return Response(serializer.data)


class ChatMessagesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, chat_id):
        # Check membership
        if not ChatMember.objects.filter(chat_id=chat_id, user=request.user).exists():
            return Response(
                {"detail": "Not a member of this chat"},
                status=status.HTTP_403_FORBIDDEN,
            )

        messages = Message.objects.filter(chat_id=chat_id)
        serializer = MessageSerializer(messages, many=True)
        return Response(serializer.data)


class CreateChatView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChatCreateSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )

        user_ids = serializer.validated_data["user_ids"]
        is_group = serializer.validated_data.get("is_group", False)
        name = serializer.validated_data.get("name")

        chat = ChatRoom.objects.create(
            is_group=is_group,
            name=name if is_group else None,
        )

        for uid in user_ids:
            ChatMember.objects.create(
                chat=chat,
                user_id=uid,
            )

        return Response(
            ChatRoomSerializer(chat).data,
            status=status.HTTP_201_CREATED,
        )