from pathlib import Path
from decouple import config
import os
from datetime import timedelta

# Base directory setup
BASE_DIR = Path(__file__).resolve().parent.parent

# Security and Debugging
SECRET_KEY = config("SECRET_KEY", default="django-insecure-development-key")  # Use a secure key in production
DEBUG = False

# ALLOWED_HOSTS: Allow the frontend and backend URLs
ALLOWED_HOSTS = [
    'pixel-classes.onrender.com', 
    'localhost', 
    '127.0.0.1', 
    'pixelclass.netlify.app',  # Updated to not include full URL 'http://localhost:5173'
]

# Installed Apps
INSTALLED_APPS = [
    'corsheaders',  # For CORS handling
    'user',  # Your app
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',  # Django REST Framework
]

# Middleware
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',  # This should be at the top of the list
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware', 
]

# Root URL configuration
ROOT_URLCONF = 'Pixel.urls'


# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'

# Use Whitenoise for serving static files with compression and caching
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Directory for collecting static files (when running `collectstatic`)
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, 'static'),  # Add the static directory at the project level
]

# For production, Django will collect all static files into this directory
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')


# Templates configuration
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'Pixel.wsgi.application'

# Database Configuration
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": config("POSTGRES_DATABASE"),
        "USER": config("POSTGRES_USER"),
        "PASSWORD": config("POSTGRES_PASSWORD"),
        "HOST": config("POSTGRES_HOST", default="127.0.0.1"),
        "PORT": config("POSTGRES_PORT", default="5432"),
    }
}

# Email Settings
EMAIL_BACKEND = config("EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = config("EMAIL_HOST", default="smtp.gmail.com")
EMAIL_PORT = config("EMAIL_PORT", default=587)
EMAIL_USE_TLS = config("EMAIL_USE_TLS", default=True)
EMAIL_HOST_USER = config("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD", default="")

# Password Validators
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Language and timezone settings
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True



# Default auto field
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# CORS Configuration
CORS_ALLOWED_ORIGINS = [
    'http://localhost:5173',  # Frontend in development
    'https://pixel-classes.onrender.com',  # Frontend hosted on Render
    'https://pixelclass.netlify.app',  # Frontend hosted on Netlify
]

CSRF_TRUSTED_ORIGINS = [
    'http://localhost:5173',
    'https://pixelclass.netlify.app',
]

# Secure CSRF cookie settings
CSRF_COOKIE_SECURE = False  # Disable for local development (HTTPS is not needed)
CSRF_COOKIE_SAMESITE = 'Strict'  # CSRF cookie should not be sent with cross-site requests

# CORS allow credentials and headers
CORS_ALLOW_CREDENTIALS = True
CORS_EXPOSE_HEADERS = ['Content-Type', 'Authorization']
CORS_ALLOW_HEADERS = [
    'content-type',
    'authorization',
    'x-csrftoken',
]

# Security headers (optional for production)
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_HSTS_SECONDS = 3600
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Enable SSL headers for proxy setup in production
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# REST Framework settings
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.UserRateThrottle',
        'rest_framework.throttling.AnonRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'user': '1000/day',
        'anon': '100/day',
    },
}

# JWT Token Lifetime settings
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=10),  # Expiry for access tokens
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),  # Expiry for refresh tokens
}

# Logging Configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': True,
        },
    },
}

