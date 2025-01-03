from django.urls import path
from .views import ResendOTPView, LoginView, RegisterView, VerifyOTPView

urlpatterns = [
    # path('resend-otp/', ResendOTPView.as_view(), name='resend_otp'),
    path('login/', LoginView.as_view(), name='login'),
    path('register/', RegisterView.as_view(), name='register'),
    path('verify-otp/', VerifyOTPView.as_view(), name='verify_otp'),
]