from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.db.models import Max, Count

from .models import ChatRoom, ChatMember, Message
from .serializers import (
    ChatRoomSerializer,
    MessageSerializer,
    ChatCreateSerializer,
)

class RecentChatsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # 1. Fetch all chats the user is in
        member_chat_ids = ChatMember.objects.filter(user=request.user).values_list('chat_id', flat=True)

        chats = (
            ChatRoom.objects
            .filter(id__in=member_chat_ids)
            .annotate(last_msg_time=Max("messages__created_at"))
            .order_by("-last_msg_time", "-created_at")
        )

        serializer = ChatRoomSerializer(chats, many=True)
        raw_data = serializer.data

        # 2. PYTHON FILTER: Remove duplicate 1-on-1 chats
        # This cleans up the "dirty data" in your database instantly for the user
        unique_data = []
        seen_partners = set()

        for chat in raw_data:
            if chat['is_group']:
                unique_data.append(chat)
            else:
                # Find the 'other' person in the chat
                partner = next(
                    (m for m in chat['members'] if m['username'] != request.user.username), 
                    None
                )
                
                if partner:
                    # If we've already seen a chat with this partner, skip this one
                    if partner['id'] in seen_partners:
                        continue
                    
                    seen_partners.add(partner['id'])
                    unique_data.append(chat)
                else:
                    # Fallback for self-chats or errors
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

        messages = Message.objects.filter(chat_id=chat_id)
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

        # ✅ STOP DUPLICATES: Check if 1-on-1 chat already exists
        if not is_group and len(user_ids) == 2:
            # Look for a chat that has both users
            # We filter for chats that contain user1 AND user2
            u1, u2 = user_ids[0], user_ids[1]
            existing_chat = (
                ChatRoom.objects.filter(is_group=False)
                .filter(members__user_id=u1)
                .filter(members__user_id=u2)
                .distinct()
                .first()
            )
            
            if existing_chat:
                # Return the existing chat instead of creating a new one
                return Response(
                    ChatRoomSerializer(existing_chat).data, 
                    status=status.HTTP_200_OK
                )

        # If no existing chat found, create new one
        chat = ChatRoom.objects.create(
            is_group=is_group,
            name=name if is_group else None,
        )

        for uid in user_ids:
            ChatMember.objects.create(chat=chat, user_id=uid)

        return Response(
            ChatRoomSerializer(chat).data,
            status=status.HTTP_201_CREATED,
        )