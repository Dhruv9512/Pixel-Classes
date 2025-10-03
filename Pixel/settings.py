import os
from pathlib import Path
from datetime import timedelta
import dj_database_url
from decouple import config
import ssl
from dotenv import load_dotenv
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# Security
SECRET_KEY = config("SECRET_KEY", default="django-insecure-development-key")
DEBUG = config("DEBUG", default=False, cast=bool)
COOKIE_SECURE = not DEBUG

ALLOWED_HOSTS = config(
    "ALLOWED_HOSTS",
    default="pixel-classes.onrender.com,127.0.0.1,localhost",
    cast=lambda v: [s.strip() for s in v.split(",")]
)

# Database
DATABASES = {
    'default': dj_database_url.config(
        default=os.getenv('DATABASE_URL'),
        conn_max_age=600,
        ssl_require=not DEBUG
    )
}

# Email
BREVO_SENDER_EMAIL = os.getenv('BREVO_SENDER_EMAIL')
BREVO_API_KEY = os.getenv('BREVO_API_KEY')
# Apps
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

# JWT
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=30),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
}

# Middleware
# Correct order for cache middleware per Django docs:
# Request path: top->bottom; Response path: bottom->top. [web:38][web:174]
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',

    # Cache: Fetch first on request, Update last on response wrapped around CommonMiddleware
    'django.middleware.cache.UpdateCacheMiddleware',     # caches the response (runs on response phase) [web:38]
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.cache.FetchFromCacheMiddleware',  # serves from cache early (request phase) [web:38]

    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.middleware.gzip.GZipMiddleware',
]

CACHE_MIDDLEWARE_SECONDS = 300
CACHE_MIDDLEWARE_KEY_PREFIX = ""  # combined with KEY_PREFIX in CACHES [web:180]
CACHE_MIDDLEWARE_KEY_FUNC = "user.utils.user_cache_key"

ROOT_URLCONF = 'Pixel.urls'
WSGI_APPLICATION = 'Pixel.wsgi.application'
ASGI_APPLICATION = 'Pixel.asgi.application'

# Channels
CHANNEL_LAYERS = {
    "default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}
}

# Static / Media
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / "static"]
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Templates
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

# Auth validators
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# I18N
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True
USE_L10N = True

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# DRF
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'user.authentication.CookieJWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.UserRateThrottle',
        'rest_framework.throttling.AnonRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'user': '100000/day',
        'anon': '10000/day',
    },
}

# Celery
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_BROKER_USE_SSL = {'ssl_cert_reqs': ssl.CERT_REQUIRED if not DEBUG else None}

# CORS/CSRF: use plain URLs (no markdown), list each allowed origin when credentials enabled. [web:178][web:184]
CORS_ALLOWED_ORIGINS = config(
    "CORS_ALLOWED_ORIGINS",
    default="https://pixel-classes.onrender.com,https://pixelclass.netlify.app,http://172.20.10.4:5173,http://localhost:5173",
    cast=lambda v: [s.strip() for s in v.split(",")]
)
CORS_ALLOW_CREDENTIALS = True
CSRF_TRUSTED_ORIGINS = config(
    "CSRF_TRUSTED_ORIGINS",
    default="https://pixelclass.netlify.app,http://172.20.10.4:5173,http://localhost:5173,https://pixel-classes.onrender.com",
    cast=lambda v: [s.strip() for s in v.split(",")]
)

# Security headers
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 3600
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {'console': {'level': 'INFO', 'class': 'logging.StreamHandler'}},
    'loggers': {
        'django': {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
        'watchdog': {'handlers': ['console'], 'level': 'WARNING', 'propagate': False},
        'rest_framework': {'handlers': ['console'], 'level': 'WARNING', 'propagate': False},
    },
}

JET_DEFAULT_THEME = 'green'

# Caching
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "my_cache_table",
        "TIMEOUT": 300,
        "KEY_PREFIX": "pixel",     # reduce collisions; combines with CACHE_MIDDLEWARE_KEY_PREFIX [web:183][web:180]
        "OPTIONS": {
            "MAX_ENTRIES": 1000,
            "CULL_FREQUENCY": 2,   # cull half when full; faster than 0 (dump all) [web:183]
        },
    }
}

# Optional: Vercel Blob Token
VERCEL_BLOB_TOKEN = os.getenv("BLOB_READ_WRITE_TOKEN")
