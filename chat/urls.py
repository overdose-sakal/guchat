from django.urls import path
from .views import RecentChatsView, ChatMessagesView, CreateChatView

urlpatterns = [
    path("recent/", RecentChatsView.as_view(), name="recent-chats"),
    path("<int:chat_id>/messages/", ChatMessagesView.as_view(), name="chat-messages"),
    path("create/", CreateChatView.as_view(), name="create-chat"),
]
