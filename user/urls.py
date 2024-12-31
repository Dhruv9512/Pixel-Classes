from django.urls import path
from .views import LoginView, RegisterView, VerifyOTPView
import views

urlpatterns = [
    path('login/', LoginView.as_view(), name="login"),
    path('register/', RegisterView.as_view(), name="register"),
    path('verify/', VerifyOTPView.as_view(), name='verify'),
    path('resend-otp/', views.resend_otp, name='resend_otp'),
]
