from rest_framework import serializers
from django.contrib.auth import authenticate
from django.utils.crypto import get_random_string
from django.utils import timezone
from django.db import transaction
from django.core.mail import send_mail
from django.conf import settings
import logging

from .models import User, EmailOTP

logger = logging.getLogger(__name__)


class RegisterSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("email", "username", "password")
        extra_kwargs = {"password": {"write_only": True}}

    def validate_email(self, value):
        """Check if email already exists"""
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def validate_username(self, value):
        """Check if username already exists"""
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("A user with this username already exists.")
        return value

    def create(self, validated_data):
        logger.info(f"🟢 Starting registration for {validated_data['email']}")
        
        try:
            # Use transaction to ensure rollback on failure
            with transaction.atomic():
                # Create user
                user = User.objects.create_user(
                    email=validated_data["email"],
                    username=validated_data["username"],
                    password=validated_data["password"],
                )
                logger.info(f"✅ User created: {user.email}")

                # Generate OTP
                otp = get_random_string(length=6, allowed_chars="0123456789")
                EmailOTP.objects.create(email=user.email, otp=otp)
                logger.info(f"✅ OTP created: {otp}")

                # Send email using Django SMTP (Gmail)
                try:
                    self.send_otp_email(user.email, otp)
                    logger.info(f"✅ Email sent to {user.email}")
                    
                except Exception as email_error:
                    # Log the specific error from Gmail/SMTP
                    logger.error(f"⚠️ Email sending failed: {str(email_error)}")
                    # In development, print OTP to console so you can still verify
                    print(f"\n\n👉 MANUALLY COPY OTP: {otp}\n\n")

                return user
                
        except serializers.ValidationError:
            raise
        except Exception as e:
            logger.error(f"❌ Registration failed: {str(e)}")
            raise serializers.ValidationError(f"Registration failed: {str(e)}")

    def send_otp_email(self, email, otp):
        """Send OTP email using Django's send_mail (uses settings.py SMTP)"""
        subject = "Your GuChat Verification Code"
        
        # HTML Message
        html_message = f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <h2 style="color: #8b5cf6;">Welcome to GuChat!</h2>
                <p>Your verification code is:</p>
                <div style="background: #f3f4f6; padding: 20px; border-radius: 8px; text-align: center; margin: 20px 0;">
                    <h1 style="color: #8b5cf6; font-size: 32px; letter-spacing: 8px; margin: 0;">{otp}</h1>
                </div>
                <p style="color: #6b7280;">This code will expire in 10 minutes.</p>
                <p style="color: #6b7280; font-size: 12px;">If you didn't request this code, please ignore this email.</p>
            </div>
        """
        
        # Plain text fallback
        plain_message = f"Welcome to GuChat! Your verification code is: {otp}"
        
        send_mail(
            subject,
            plain_message,
            settings.DEFAULT_FROM_EMAIL,
            [email],
            html_message=html_message,
            fail_silently=False, # This ensures errors are raised if SMTP fails
        )


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