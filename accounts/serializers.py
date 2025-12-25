from rest_framework import serializers
from django.contrib.auth import authenticate
from django.utils.crypto import get_random_string
from django.utils import timezone
from django.db import transaction
import logging
import requests  # Required to hit EmailJS API
import os

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
            # Atomic transaction: if any part fails, roll back everything
            with transaction.atomic():
                # 1. Create the user
                user = User.objects.create_user(
                    email=validated_data["email"],
                    username=validated_data["username"],
                    password=validated_data["password"],
                )
                logger.info(f"✅ User created: {user.email}")

                # 2. Generate the 6-digit OTP
                otp = get_random_string(length=6, allowed_chars="0123456789")
                EmailOTP.objects.create(email=user.email, otp=otp)
                logger.info(f"✅ OTP generated (logged for backup): {otp}")

                # 3. Send via EmailJS API
                # We wrap this in a try/except so email failure doesn't crash the user creation
                # (You can still find the OTP in logs if email fails)
                try:
                    self.send_email_via_emailjs(user.email, user.username, otp)
                except Exception as e:
                    logger.error(f"⚠️ Email sending sequence failed: {str(e)}")

                return user
                
        except serializers.ValidationError:
            raise
        except Exception as e:
            logger.error(f"❌ Registration process failed: {str(e)}")
            raise serializers.ValidationError(f"Registration failed: {str(e)}")

    def send_email_via_emailjs(self, email, username, otp):
        """
        Sends email using EmailJS REST API.
        This uses HTTP (Port 443) which works on Render Free Tier.
        """
        service_id = os.environ.get('EMAILJS_SERVICE_ID')
        template_id = os.environ.get('EMAILJS_TEMPLATE_ID')
        public_key = os.environ.get('EMAILJS_PUBLIC_KEY')
        private_key = os.environ.get('EMAILJS_PRIVATE_KEY')

        # Check if environment variables are set
        if not all([service_id, template_id, public_key, private_key]):
            logger.error("⚠️ EmailJS Env Vars missing! Cannot send email.")
            return

        url = "https://api.emailjs.com/api/v1.0/email/send"
        
        # Payload matches the variables in your HTML template
        payload = {
            "service_id": service_id,
            "template_id": template_id,
            "user_id": public_key,      # This is your Public Key
            "accessToken": private_key, # This is your Private Key (Required for backend use)
            "template_params": {
                "to_email": email,      # Maps to {{to_email}} in Settings
                "username": username,    # Maps to {{username}} in HTML
                "otp": otp              # Maps to {{otp}} in HTML
            }
        }

        # Send the request
        response = requests.post(url, json=payload, timeout=10)
        
        if response.status_code == 200:
            logger.info(f"📧 Email successfully sent to {email} via EmailJS")
        else:
            logger.error(f"⚠️ EmailJS Failed ({response.status_code}): {response.text}")


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