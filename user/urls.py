from django.urls import path
from .views import ResendOTPView, LoginView, RegisterView, VerifyOTPView,PasswordResetRequestView, PasswordResetConfirmView, SubmitNewPasswordView, PasswordResetStatusView

urlpatterns = [
    path('login/', LoginView.as_view(), name='login'),
    path('register/', RegisterView.as_view(), name='register'),
    path('verify-otp/', VerifyOTPView.as_view(), name='verify_otp'),
    path('resend-otp/', ResendOTPView.as_view(), name='resend_otp'),
    path('password_reset/', PasswordResetRequestView.as_view(), name='password_reset'),
    path('reset/<int:user_id>/<str:token>/', PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('reset/status/', PasswordResetStatusView.as_view(), name='password_reset_status'),
    path('submit-new-password/', SubmitNewPasswordView.as_view(), name='SubmitNewPasswordView'),

]