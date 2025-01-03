from django.urls import path
from .views import LoginView, RegisterView, VerifyOTPView


urlpatterns = [
    path('login/', LoginView.as_view(), name="login"),
    path('register/', RegisterView.as_view(), name="register"),
    path('verify/', VerifyOTPView.as_view(), name='verify'),
    # path('resend-otp/', ResendOTPView.as_view(), name='resend_otp'),
]