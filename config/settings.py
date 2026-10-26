"""
Django settings for config project.
"""
import os
import dj_database_url
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY: Load SECRET_KEY from environment variable
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'django-insecure-#g@h(kn8i1p0l-dws(-o+m58n+5py(th*43(wd$)vhnd!9*nn-')

# TEMPORARY: Turned on to diagnose the 500 error on Render
# We will change this back to False once the issue is fixed!
DEBUG = True

# SECURITY: Explicitly allow your Render domain and localhost
ALLOWED_HOSTS = [
    '127.0.0.1',
    'localhost',
    'voting-system-mh0m.onrender.com',
    '.onrender.com'
]

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Custom Apps
    'apps.authentication',
    'apps.dashboard',
    'apps.elections',
    'apps.voters',
    'apps.candidates',
    'apps.voting',
    'apps.blockchain',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

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

WSGI_APPLICATION = 'config.wsgi.application'

# DATABASES: Use Neon PostgreSQL on Render, SQLite locally
if 'RENDER' in os.environ:
    DATABASES = {
        'default': dj_database_url.config(
            env='DATABASE_URL',
            conn_max_age=600,
            ssl_require=True
        )
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript)
STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Django 4.2+ Modern Static Files Storage Configuration
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

# Media files (Party Logos, Candidate Photos)
MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Authentication Redirects
LOGIN_REDIRECT_URL = 'dashboard:home'
LOGIN_URL = 'authentication:login'
LOGOUT_REDIRECT_URL = 'authentication:login'

# Prototype Mode
PROTOTYPE_MODE = True