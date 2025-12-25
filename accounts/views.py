from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model

User = get_user_model()


from .serializers import (
    RegisterSerializer,
    VerifyOTPSerializer,
    LoginSerializer,
    MeSerializer,
)


# class RegisterView(APIView):
#     def post(self, request):
#         serializer = RegisterSerializer(data=request.data)
#         serializer.is_valid(raise_exception=True)
#         serializer.save()
#         return Response(
#             {"message": "OTP sent to email"},
#             status=status.HTTP_201_CREATED,
#         )


class RegisterView(APIView):
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)

        if not serializer.is_valid():
            print("❌ REGISTER ERRORS:", serializer.errors)
            return Response(serializer.errors, status=400)



class VerifyOTPView(APIView):
    def post(self, request):
        serializer = VerifyOTPSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(
            {"message": "Email verified successfully"},
            status=status.HTTP_200_OK,
        )


class LoginView(APIView):
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data["user"]
        refresh = RefreshToken.for_user(user)

        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            },
            status=status.HTTP_200_OK,
        )


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = MeSerializer(request.user)
        return Response(serializer.data)


from django.db.models import Q
from rest_framework.permissions import IsAuthenticated
from .serializers import UserSearchSerializer


class UserSearchView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        query = request.GET.get("search", "")
        users = (
            User.objects
            .filter(username__icontains=query)
            .exclude(id=request.user.id)
        )

        serializer = UserSearchSerializer(users, many=True)
        return Response(serializer.data)
