import os
from pathlib import Path

import environ

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Initialize environment variables
env = environ.Env(
    DEBUG=(bool, False),
    SECRET_KEY=(str, 'django-insecure-default-fallback-key-for-dev'),
    ALLOWED_HOSTS=(list, ['localhost', '127.0.0.1', 'backend']),
)

# Read .env file from the project root (parent directory of BASE_DIR) or fallback to BASE_DIR
env_file = os.path.join(BASE_DIR.parent, '.env')
if os.path.exists(env_file):
    environ.Env.read_env(env_file)
elif os.path.exists(os.path.join(BASE_DIR, '.env')):
    environ.Env.read_env(os.path.join(BASE_DIR, '.env'))

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.0/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env('SECRET_KEY')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env('DEBUG')

ALLOWED_HOSTS = env('ALLOWED_HOSTS')

# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Third-party packages
    'rest_framework',
    'corsheaders',

    # LedgerPro v2 Apps
    'accounts',
    'firms',
    'invoices',
    'trade_docs',
    'vault',
    'analytics',
    'eway_bills',
    'audit',
    'security',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'ledgerpro_backend.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
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

WSGI_APPLICATION = 'ledgerpro_backend.wsgi.application'
ASGI_APPLICATION = 'ledgerpro_backend.asgi.application'

# Database
# https://docs.djangoproject.com/en/5.0/ref/settings/#databases
# Fallback to SQLite if not running inside Docker Compose (i.e. DB_HOST is not 'db')
USE_SQLITE = os.environ.get('USE_SQLITE') == 'True' or (env('DB_HOST', default='') != 'db' and not os.environ.get('DATABASE_URL'))

if USE_SQLITE:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }
else:
    DATABASES = {
        'default': env.db(
            'DATABASE_URL',
            default=f"postgres://{env('DB_USER', default='ledgerpro_user')}:{env('DB_PASSWORD', default='ledgerpro_secure_password')}@{env('DB_HOST', default='db')}:{env('DB_PORT', default='5432')}/{env('DB_NAME', default='ledgerpro_db')}"
        )
    }

AUTH_USER_MODEL = 'accounts.User'

# Password validation
# https://docs.djangoproject.com/en/5.0/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
# https://docs.djangoproject.com/en/5.0/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.0/howto/static-files/

STATIC_URL = 'static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')

# Default primary key field type
# https://docs.djangoproject.com/en/5.0/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Celery Configurations
CELERY_BROKER_URL = env('REDIS_URL', default='redis://redis:6379/0')
CELERY_RESULT_BACKEND = env('REDIS_URL', default='redis://redis:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'UTC'
CELERY_TASK_ALWAYS_EAGER = USE_SQLITE

# Media files (Uploaded invoices/docs)
MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

# CORS Configurations
CORS_ALLOW_ALL_ORIGINS = True # Allow all in development, restrict for production
CORS_ALLOW_CREDENTIALS = True

# Django REST Framework Settings
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'accounts.authentication.SignedTokenAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
}

# ── Email / SMTP Configuration ────────────────────────────────────────────────
# Configure via .env: EMAIL_HOST, EMAIL_PORT, EMAIL_HOST_USER, EMAIL_HOST_PASSWORD
# Example for Gmail:
#   EMAIL_HOST=smtp.gmail.com
#   EMAIL_PORT=587
#   EMAIL_HOST_USER=yourname@gmail.com
#   EMAIL_HOST_PASSWORD=your_app_password
#   EMAIL_USE_TLS=True
#   DEFAULT_FROM_EMAIL=LedgerPro <yourname@gmail.com>
EMAIL_BACKEND = env('EMAIL_BACKEND', default='django.core.mail.backends.smtp.EmailBackend')
EMAIL_HOST = env('EMAIL_HOST', default='')
EMAIL_PORT = env.int('EMAIL_PORT', default=587)
EMAIL_HOST_USER = env('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = env('EMAIL_HOST_PASSWORD', default='')
EMAIL_USE_TLS = env.bool('EMAIL_USE_TLS', default=True)
EMAIL_USE_SSL = env.bool('EMAIL_USE_SSL', default=False)
DEFAULT_FROM_EMAIL = env('DEFAULT_FROM_EMAIL', default='LedgerPro <noreply@ledgerpro.in>')

# ── Google OAuth 2.0 ──────────────────────────────────────────────────────────
# Create credentials at: https://console.cloud.google.com/apis/credentials
# Set the Authorized Redirect URI to:  http://localhost:8000/api/auth/google/callback
# (or your production domain equivalent)
GOOGLE_OAUTH_CLIENT_ID = env('GOOGLE_OAUTH_CLIENT_ID', default='')
GOOGLE_OAUTH_CLIENT_SECRET = env('GOOGLE_OAUTH_CLIENT_SECRET', default='')
GOOGLE_OAUTH_REDIRECT_URI = env(
    'GOOGLE_OAUTH_REDIRECT_URI',
    default='http://localhost:3000/auth/google/callback'
)

# Resend API key (optional — only needed if not using SMTP)
RESEND_API_KEY = env('RESEND_API_KEY', default='')

