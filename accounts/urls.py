from django.urls import path
from .views import RegisterView, VerifyOTPView, LoginView, MeView, UserSearchView

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("verify-otp/", VerifyOTPView.as_view(), name="verify-otp"),
    path("login/", LoginView.as_view(), name="login"),
    path("me/", MeView.as_view(), name="me"),
    path("users/", UserSearchView.as_view(), name="user-search"),

]
