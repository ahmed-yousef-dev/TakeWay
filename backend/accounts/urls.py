from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from accounts.views import (
    ChangePasswordView,
    ForgotPasswordView,
    LoginView,
    ProfileView,
    RequestOTPView,
    VerifyOTPView,
)

urlpatterns = [
    path("otp/request/", RequestOTPView.as_view(), name="otp-request"),
    path("otp/verify/", VerifyOTPView.as_view(), name="otp-verify"),
    path("login/", LoginView.as_view(), name="login"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("password/reset/", ForgotPasswordView.as_view(), name="password-reset"),
    path("password/change/", ChangePasswordView.as_view(), name="password-change"),
    path("profile/", ProfileView.as_view(), name="user-profile"),
]
