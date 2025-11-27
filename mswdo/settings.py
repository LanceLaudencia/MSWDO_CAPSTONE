import os
from pathlib import Path

# Convert BASE_DIR to Path so Django can safely use '/'
BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = 'testsecretkey123'
DEBUG = True
ALLOWED_HOSTS = ['*']

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'core',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
]

ROOT_URLCONF = 'mswdo.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        # Updated: BASE_DIR is a Path so join works cleanly
        'DIRS': [BASE_DIR / 'core' / 'templates'],
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

WSGI_APPLICATION = 'mswdo.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Custom user model
AUTH_USER_MODEL = 'core.User'

# -------------------------
# STATIC & MEDIA FIX
# -------------------------

STATIC_URL = '/static/'
STATICFILES_DIRS = [
    BASE_DIR / "static",   # for your project-wide static files
]
STATIC_ROOT = BASE_DIR / "staticfiles"  # where Django collects static

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'         # <-- fully fixed

# -------------------------
# EMAIL CONFIG
# -------------------------

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "smtp.gmail.com"
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = "jefflaud19@gmail.com"
EMAIL_HOST_PASSWORD = "uixs nxil lybq mqio"  # consider moving to env variable
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER


STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"