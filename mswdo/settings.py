from pathlib import Path
import pymysql
pymysql.install_as_MySQLdb()

# ======================
# BASE DIRECTORY
# ======================
BASE_DIR = Path(__file__).resolve().parent.parent


# ======================
# SECURITY
# ======================
SECRET_KEY = 'testsecretkey123'  # move to env in production
DEBUG = True
ALLOWED_HOSTS = [
    "localhost",
    "127.0.0.1",
    "mswdo.ormin.cloud",]


# ======================
# APPLICATIONS
# ======================
INSTALLED_APPS = [
    # Django default
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    

    # Third-party
    'rest_framework',
    'corsheaders',

    # Local apps
    'core',
]


# ======================
# MIDDLEWARE
# ======================
MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',  # MUST be first
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]


# ======================
# CORS
# ======================
CORS_ALLOWED_ORIGINS = [
    "http://localhost:5178",
]

CORS_ALLOW_CREDENTIALS = True

CSRF_TRUSTED_ORIGINS = [
    "http://localhost:5178",
    "https://mswdo.ormin.cloud",
]



# ======================
# URLS / WSGI
# ======================
ROOT_URLCONF = 'mswdo.urls'

WSGI_APPLICATION = 'mswdo.wsgi.application'


# ======================
# TEMPLATES
# ======================
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'core' / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'core.context_processors.notifications_processor',
            ],
        },
    },
]


# ======================
# DATABASE
# ======================
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'mswdo-db',
        'USER': 'mswdo_user',
        'PASSWORD': 'MSWDO_Password123',
        'HOST': 'mswdo-database-4hecyw',
        'PORT': '3306',
        'OPTIONS': {
            'charset': 'utf8mb4',
        },
    }
}



# ======================
# AUTH
# ======================
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

AUTH_USER_MODEL = 'core.User'



# ======================
# INTERNATIONALIZATION
# ======================
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Manila'
USE_I18N = True
USE_TZ = False


# ======================
# STATIC FILES
# ======================
STATIC_URL = '/static/'
STATICFILES_DIRS = [
    BASE_DIR / 'core' / 'static',
]
STATIC_ROOT = BASE_DIR / 'staticfiles'


# ======================
# MEDIA FILES
# ======================
import os

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')


# ======================
# EMAIL
# ======================
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'jefflaud19@gmail.com'
EMAIL_HOST_PASSWORD = 'uixs nxil lybq mqio'  # move to env variable
DEFAULT_FROM_EMAIL = EMAIL_HOST_USER


# ======================
# SMS
# ======================

PHILSMS_API_TOKEN = "2052|E0nWs3IxaqRsOeQeP904ExTLnhcIxkntuQS8KvJT271a4066"
PHILSMS_SENDER_ID = "PhilSMS"



# ======================
# DEFAULT PRIMARY KEY
# ======================
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


LOGIN_URL = 'client_login'
LOGIN_REDIRECT_URL = 'client_dashboard'


