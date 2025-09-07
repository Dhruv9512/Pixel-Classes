import os
from pathlib import Path
from datetime import timedelta
import dj_database_url
from decouple import config
import ssl

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# ----------------------
# BASE DIRECTORY
# ----------------------
BASE_DIR = Path(__file__).resolve().parent.parent

# ----------------------
# SECURITY
# ----------------------
SECRET_KEY = config("SECRET_KEY", default="django-insecure-development-key")
DEBUG = config("DEBUG", default=False, cast=bool)

# Decide cookie security dynamically
COOKIE_SECURE = False if DEBUG else True

ALLOWED_HOSTS = config(
    "ALLOWED_HOSTS",
    default="pixel-classes.onrender.com,127.0.0.1,localhost",
    cast=lambda v: [s.strip() for s in v.split(",")]
)


# ----------------------
# CSRF / SESSION SECURITY
# ----------------------
CSRF_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_SAMESITE = 'Lax'

# ----------------------
# DATABASE CONFIGURATION
# ----------------------
DATABASES = {
    'default': dj_database_url.config(
        default=os.getenv('DATABASE_URL'),
        conn_max_age=600,
        ssl_require=not DEBUG
    )
}

# ----------------------
# EMAIL CONFIGURATION
# ----------------------
EMAIL_BACKEND = config("EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = config("EMAIL_HOST", default="smtp.gmail.com")
EMAIL_PORT = config("EMAIL_PORT", default=587, cast=int)
EMAIL_USE_TLS = config("EMAIL_USE_TLS", default=True, cast=bool)
EMAIL_HOST_USER = config("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD", default="")

# ----------------------
# APPLICATIONS
# ----------------------
INSTALLED_APPS = [
    'jet', 
    'Profile',
    'corsheaders', 
    'user',
    'home',
    'core',
    'chatting',  
    'channels',  
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',      
]



from datetime import timedelta

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=15),      # short-lived access token
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),         # long-lived refresh token
    'ROTATE_REFRESH_TOKENS': True,                       # issue new refresh token on refresh
    'BLACKLIST_AFTER_ROTATION': True,                    # invalidate old refresh tokens
}

# ----------------------
# MIDDLEWARE
# ----------------------
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.cache.UpdateCacheMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.cache.FetchFromCacheMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.middleware.gzip.GZipMiddleware',
]

CACHE_MIDDLEWARE_SECONDS = 300
CACHE_MIDDLEWARE_KEY_PREFIX = ""
CACHE_MIDDLEWARE_KEY_FUNC = "user.utils.user_cache_key"

ROOT_URLCONF = 'Pixel.urls'
WSGI_APPLICATION = 'Pixel.wsgi.application'
ASGI_APPLICATION = 'Pixel.asgi.application'

# ----------------------
# CHANNELS
# ----------------------
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer"
    }
}

# ----------------------
# STATIC / MEDIA FILES
# ----------------------
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / "static"]
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# ----------------------
# TEMPLATES
# ----------------------
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

# ----------------------
# AUTHENTICATION
# ----------------------
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# ----------------------
# INTERNATIONALIZATION
# ----------------------
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True
USE_L10N = True

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# ----------------------
# REST FRAMEWORK
# ----------------------
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
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


# ----------------------
# CELERY CONFIGURATION
# ----------------------
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_TASK_EAGER_PROPAGATES = True

# Use SSL properly in production
CELERY_BROKER_USE_SSL = {
    'ssl_cert_reqs': ssl.CERT_REQUIRED if not DEBUG else None
}

# ----------------------
# CORS
# ----------------------
CORS_ALLOWED_ORIGINS = config(
    "CORS_ALLOWED_ORIGINS",
    default="https://pixel-classes.onrender.com,https://pixelclass.netlify.app,http://172.20.10.4:5173,http://localhost:5173",
    cast=lambda v: [s.strip() for s in v.split(",")]
)

CORS_ALLOW_CREDENTIALS = True
CORS_EXPOSE_HEADERS = ['Content-Type', 'Authorization']
CORS_ALLOW_HEADERS = ['content-type', 'authorization', 'x-csrftoken']

CSRF_TRUSTED_ORIGINS = config(
    "CSRF_TRUSTED_ORIGINS",
    default="https://pixelclass.netlify.app,http://172.20.10.4:5173,http://localhost:5173",
    cast=lambda v: [s.strip() for s in v.split(",")]
)

# ----------------------
# SECURITY HEADERS
# ----------------------
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 3600
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# ----------------------
# LOGGING
# ----------------------
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {'level': 'INFO', 'class': 'logging.StreamHandler'},
    },
    'loggers': {
        'django': {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
        'watchdog': {'handlers': ['console'], 'level': 'WARNING', 'propagate': False},
        'rest_framework': {'handlers': ['console'], 'level': 'WARNING', 'propagate': False},
    },
}

# ----------------------
# JET ADMIN THEME
# ----------------------
JET_DEFAULT_THEME = 'green'

# ----------------------
# CACHING
# ----------------------
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "my_cache_table",
        "TIMEOUT": 300,
        "OPTIONS": {"MAX_ENTRIES": 1000},
    }
}

# ----------------------
# Optional: Vercel Blob Token
# ----------------------
VERCEL_BLOB_TOKEN = os.getenv("BLOB_READ_WRITE_TOKEN")
