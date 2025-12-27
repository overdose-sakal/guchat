from rest_framework import serializers
from django.contrib.auth import authenticate
from django.utils.crypto import get_random_string
from django.utils import timezone
from django.db import transaction
import logging
import requests
import os
import base64
import cloudinary
import cloudinary.uploader

from .models import User, EmailOTP

logger = logging.getLogger(__name__)

# Configure Cloudinary
cloudinary.config(
    cloud_name=os.environ.get('CLOUDINARY_CLOUD_NAME', 'your_cloud_name'),
    api_key=os.environ.get('CLOUDINARY_API_KEY', '461146461426353'),
    api_secret=os.environ.get('CLOUDINARY_API_SECRET', 'XJD2zzC9w3zZyiSnCT28fFOtwn0')
)


class RegisterSerializer(serializers.ModelSerializer):
    profile_picture_data = serializers.CharField(required=False, write_only=True, allow_blank=True)
    
    class Meta:
        model = User
        fields = ("email", "username", "name", "password", "profile_picture_data")
        extra_kwargs = {
            "password": {"write_only": True},
            "name": {"required": False}
        }

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
        
        # Extract profile picture data if provided
        profile_picture_data = validated_data.pop('profile_picture_data', None)
        
        try:
            with transaction.atomic():
                # Upload profile picture to Cloudinary if provided
                profile_picture_url = None
                if profile_picture_data:
                    try:
                        profile_picture_url = self.upload_to_cloudinary(
                            profile_picture_data, 
                            validated_data['username']
                        )
                        logger.info(f"✅ Profile picture uploaded: {profile_picture_url}")
                    except Exception as e:
                        logger.error(f"⚠️ Profile picture upload failed: {str(e)}")
                        # Continue with registration even if image upload fails

                # Create user
                user = User.objects.create_user(
                    email=validated_data["email"],
                    username=validated_data["username"],
                    password=validated_data["password"],
                    name=validated_data.get("name", ""),
                    profile_picture=profile_picture_url
                )
                logger.info(f"✅ User created: {user.email}")

                # Generate OTP
                otp = get_random_string(length=6, allowed_chars="0123456789")
                EmailOTP.objects.create(email=user.email, otp=otp)
                logger.info(f"✅ OTP generated")

                # Send email via EmailJS
                try:
                    self.send_email_via_emailjs(user.email, user.username, otp)
                except Exception as e:
                    logger.error(f"⚠️ Email sending failed: {str(e)}")
                    logger.warning(f"🔑 OTP for {user.email}: {otp}")

                return user
                
        except serializers.ValidationError:
            raise
        except Exception as e:
            logger.error(f"❌ Registration failed: {str(e)}")
            raise serializers.ValidationError(f"Registration failed: {str(e)}")

    def upload_to_cloudinary(self, base64_data, username):
        """Upload base64 image to Cloudinary"""
        try:
            # Remove data URL prefix if present
            if 'base64,' in base64_data:
                base64_data = base64_data.split('base64,')[1]
            
            # Upload to Cloudinary
            response = cloudinary.uploader.upload(
                f"data:image/png;base64,{base64_data}",
                folder="guchat/profiles",
                public_id=f"user_{username}_{int(timezone.now().timestamp())}",
                overwrite=True,
                resource_type="image",
                transformation=[
                    {'width': 400, 'height': 400, 'crop': 'fill', 'gravity': 'face'},
                    {'quality': 'auto:good'}
                ]
            )
            
            return response['secure_url']
        except Exception as e:
            logger.error(f"Cloudinary upload error: {str(e)}")
            raise

    def send_email_via_emailjs(self, email, username, otp):
        """Send OTP email using EmailJS REST API"""
        service_id = os.environ.get('EMAILJS_SERVICE_ID')
        template_id = os.environ.get('EMAILJS_TEMPLATE_ID')
        public_key = os.environ.get('EMAILJS_PUBLIC_KEY')
        private_key = os.environ.get('EMAILJS_PRIVATE_KEY')

        if not all([service_id, template_id, public_key, private_key]):
            logger.error("⚠️ EmailJS Env Vars missing!")
            return

        url = "https://api.emailjs.com/api/v1.0/email/send"
        
        payload = {
            "service_id": service_id,
            "template_id": template_id,
            "user_id": public_key,
            "accessToken": private_key,
            "template_params": {
                "to_email": email,
                "username": username,
                "otp": otp
            }
        }

        response = requests.post(url, json=payload, timeout=10)
        
        if response.status_code == 200:
            logger.info(f"📧 Email sent to {email}")
        else:
            logger.error(f"⚠️ EmailJS Failed: {response.text}")


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
    display_name = serializers.ReadOnlyField()
    
    class Meta:
        model = User
        fields = ("id", "email", "username", "name", "profile_picture", "display_name", "is_verified")


class UserSearchSerializer(serializers.ModelSerializer):
    display_name = serializers.ReadOnlyField()
    
    class Meta:
        model = User
        fields = ("id", "username", "name", "profile_picture", "display_name")


from rest_framework import serializers
from django.contrib.auth import get_user_model

User = get_user_model()

# ✅ ADD THIS SERIALIZER
class UserUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('display_name', 'profile_picture')
        extra_kwargs = {
            'display_name': {'required': False},
            'profile_picture': {'required': False},
        }

# (Ensure UserPublicSerializer is also here if you use it in accounts/views.py)
class UserPublicSerializer(serializers.ModelSerializer):
    display_name = serializers.ReadOnlyField()
    
    class Meta:
        model = User
        fields = ("id", "username", "display_name", "profile_picture")