from django.urls import path
from .views import ResendOTPView, LoginView,LogoutView, RegisterView, VerifyOTPView,PasswordResetRequestView, GoogleSignupAPIView,PasswordResetConfirmView,SubmitNewPasswordView, PasswordResetStatusView , SendCuteEmail , GoogleLoginAPIView

urlpatterns = [
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('register/', RegisterView.as_view(), name='register'),
    path('verify-otp/', VerifyOTPView.as_view(), name='verify_otp'),
    path('resend-otp/', ResendOTPView.as_view(), name='resend_otp'),
    path('password_reset/', PasswordResetRequestView.as_view(), name='password_reset'),
    path('reset/<int:user_id>/<str:token>/', PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('reset/status/', PasswordResetStatusView.as_view(), name='password_reset_status'),
    path('submit-new-password/', SubmitNewPasswordView.as_view(), name='SubmitNewPasswordView'),
    path('Mitsuha/',SendCuteEmail.as_view(),name='SendCuteEmail'),
    path('google-login/', GoogleLoginAPIView.as_view(), name='google-login'),
    path('google-signup/', GoogleSignupAPIView.as_view(), name='google-signup'),
]