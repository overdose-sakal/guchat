from rest_framework import serializers
from django.contrib.auth import authenticate
from django.utils.crypto import get_random_string
from django.utils import timezone

from .models import User, EmailOTP


class RegisterSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("email", "username", "password")
        extra_kwargs = {"password": {"write_only": True}}

    def create(self, validated_data):
        
        print("REGISTER SERIALIZER HIT")

        user = User.objects.create_user(
            email=validated_data["email"],
            username=validated_data["username"],
            password=validated_data["password"],
        )

        otp = get_random_string(length=6, allowed_chars="0123456789")
        EmailOTP.objects.create(email=user.email, otp=otp)

        # Email sending will be added later (SMTP / console backend for now)
        from django.core.mail import send_mail

        send_mail(
            subject="Your GuChat OTP",
            message=f"Your OTP is {otp}. It expires in 10 minutes.",
            from_email=None,
            recipient_list=[user.email],
            fail_silently=False,
        )


        return user


class VerifyOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(max_length=6)

    def validate(self, attrs):
        email = attrs["email"]
        otp = attrs["otp"]

        try:
            record = EmailOTP.objects.get(email=email, otp=otp)
        except EmailOTP.DoesNotExist:
            raise serializers.ValidationError("Invalid OTP")

        if record.is_expired():
            record.delete()
            raise serializers.ValidationError("OTP expired")

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise serializers.ValidationError("User not found")

        if user.is_verified:
            raise serializers.ValidationError("User already verified")

        attrs["user"] = user
        attrs["otp_record"] = record
        return attrs

    def save(self):
        user = self.validated_data["user"]
        otp_record = self.validated_data["otp_record"]

        user.is_verified = True
        user.save()

        otp_record.delete()
        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        user = authenticate(
            email=attrs["email"],
            password=attrs["password"],
        )

        if not user:
            raise serializers.ValidationError("Invalid credentials")

        if not user.is_verified:
            raise serializers.ValidationError("Email not verified")

        attrs["user"] = user
        return attrs


class MeSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "email", "username", "is_verified")




class UserSearchSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "username")

