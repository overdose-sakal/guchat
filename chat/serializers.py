# chat/views.py

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.db.models import Max
from django.utils import timezone

from .models import ChatRoom, ChatMember, Message
from .serializers import (
    ChatRoomSerializer,
    MessageSerializer,
    ChatCreateSerializer,
)


class RecentChatsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        member_chat_ids = (
            ChatMember.objects
            .filter(user=request.user)
            .values_list("chat_id", flat=True)
        )

        chats = (
            ChatRoom.objects
            .filter(id__in=member_chat_ids)
            # ✅ OPTIMIZATION: Prefetch user data to prevent N+1 queries in serializer
            .prefetch_related("members__user") 
            .annotate(last_msg_time=Max("messages__created_at"))
            .order_by("-last_msg_time", "-created_at")
        )

        results = []

        for chat in chats:
            chat.latest_message = (
                Message.objects
                .filter(chat=chat)
                .select_related("sender")
                .order_by("-created_at")
                .first()
            )

            chat.current_user_membership = (
                ChatMember.objects
                .filter(chat=chat, user=request.user)
                .only("last_read_at")
                .first()
            )

            results.append(chat)

        serializer = ChatRoomSerializer(
            results,
            many=True,
            context={"request": request},
        )
        raw_data = serializer.data

        unique_data = []
        seen_partners = set()

        for chat in raw_data:
            if chat["is_group"]:
                unique_data.append(chat)
                continue

            partner = next(
                (
                    m for m in chat["members"]
                    if m["username"] != request.user.username
                ),
                None,
            )

            if partner:
                if partner["id"] in seen_partners:
                    continue
                seen_partners.add(partner["id"])
                unique_data.append(chat)
            else:
                unique_data.append(chat)

        return Response(unique_data)


class ChatMessagesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, chat_id):
        if not ChatMember.objects.filter(chat_id=chat_id, user=request.user).exists():
            return Response(
                {"detail": "Not a member of this chat"},
                status=status.HTTP_403_FORBIDDEN,
            )

        ChatMember.objects.filter(
            chat_id=chat_id,
            user=request.user,
        ).update(last_read_at=timezone.now())

        messages = (
            Message.objects
            .filter(chat_id=chat_id)
            .select_related("sender")
            .order_by("-created_at")[:50]
        )

        messages = reversed(messages)

        serializer = MessageSerializer(messages, many=True)
        return Response(serializer.data)


class CreateChatView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChatCreateSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user_ids = serializer.validated_data["user_ids"]
        is_group = serializer.validated_data.get("is_group", False)
        name = serializer.validated_data.get("name")

        if not is_group and len(user_ids) == 2:
            u1, u2 = user_ids
            existing_chat = (
                ChatRoom.objects
                .filter(is_group=False)
                .filter(members__user_id=u1)
                .filter(members__user_id=u2)
                .distinct()
                .first()
            )

            if existing_chat:
                return Response(
                    ChatRoomSerializer(
                        existing_chat,
                        context={"request": request},
                    ).data,
                    status=status.HTTP_200_OK,
                )

        chat = ChatRoom.objects.create(
            is_group=is_group,
            name=name if is_group else None,
        )

        for uid in user_ids:
            ChatMember.objects.create(chat=chat, user_id=uid)

        return Response(
            ChatRoomSerializer(
                chat,
                context={"request": request},
            ).data,
            status=status.HTTP_201_CREATED,
        )