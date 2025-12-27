from django.urls import path
# ✅ Update the import to include UpdateProfileView
from .views import (
    RegisterView, 
    VerifyOTPView, 
    LoginView, 
    UpdateProfileView,  # Changed from MeView
    UserSearchView
)

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("verify-otp/", VerifyOTPView.as_view(), name="verify-otp"),
    path("login/", LoginView.as_view(), name="login"),
    
    # ✅ Map 'me/' to the new view that allows editing
    path("me/", UpdateProfileView.as_view(), name="me"), 
    
    path("users/", UserSearchView.as_view(), name="user-search"),
]