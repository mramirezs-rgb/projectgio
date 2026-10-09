import os
from datetime import timedelta
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BASE_DIR.parent


def _cargar_dotenv(ruta):
    if not ruta.exists():
        return
    for linea in ruta.read_text(encoding='utf-8').splitlines():
        linea = linea.strip()
        if not linea or linea.startswith('#') or '=' not in linea:
            continue
        clave, _, valor = linea.partition('=')
        os.environ.setdefault(clave.strip(), valor.strip().strip('"').strip("'"))


_cargar_dotenv(BASE_DIR / '.env')


def env(nombre, defecto=None):
    valor = os.environ.get(nombre)
    return valor if valor not in (None, '') else defecto


def env_bool(nombre, defecto=False):
    valor = env(nombre)
    if valor is None:
        return defecto
    return valor.strip().lower() in ('1', 'true', 'yes', 'on', 'si')


def env_int(nombre, defecto):
    try:
        return int(env(nombre, defecto))
    except (TypeError, ValueError):
        return defecto


def env_list(nombre, defecto=()):
    valor = env(nombre)
    if valor is None:
        return list(defecto)
    return [item.strip() for item in valor.split(',') if item.strip()]


DEBUG = env_bool('GIO_DEBUG', True)

SECRET_KEY = env('GIO_SECRET_KEY')
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured('GIO_SECRET_KEY es obligatoria cuando GIO_DEBUG=0.')
    SECRET_KEY = 'django-insecure-solo-para-desarrollo-local-no-usar-en-produccion'

ALLOWED_HOSTS = env_list('GIO_ALLOWED_HOSTS', ['localhost', '127.0.0.1', '[::1]'] if DEBUG else [])
CSRF_TRUSTED_ORIGINS = env_list('GIO_CSRF_TRUSTED_ORIGINS')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'django_filters',
    'corsheaders',
    'usuarios',
    'gio_app',
]

AUTH_USER_MODEL = 'usuarios.UsuarioGIO'

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

CORS_ALLOWED_ORIGINS = env_list('GIO_CORS_ORIGINS', [
    'http://localhost:5173',
    'http://127.0.0.1:5173',
    'http://localhost:4173',
    'http://127.0.0.1:4173',
])
CORS_ALLOW_CREDENTIALS = False

ROOT_URLCONF = 'backend.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'backend.wsgi.application'
ASGI_APPLICATION = 'backend.asgi.application'

if env('GIO_DB_ENGINE', 'postgresql') == 'sqlite':
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': env('GIO_DB_NAME', str(BASE_DIR / 'db.sqlite3')),
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': env('GIO_DB_NAME', 'sistema_gio'),
            'USER': env('GIO_DB_USER', 'postgres'),
            'PASSWORD': env('GIO_DB_PASSWORD', '123456'),
            'HOST': env('GIO_DB_HOST', 'localhost'),
            'PORT': env('GIO_DB_PORT', '5432'),
            'CONN_MAX_AGE': env_int('GIO_DB_CONN_MAX_AGE', 60),
        }
    }

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
     'OPTIONS': {'min_length': 8}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'es-mx'
TIME_ZONE = 'America/Mexico_City'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = 'media/'
MEDIA_ROOT = Path(env('GIO_MEDIA_ROOT', str(BASE_DIR / 'media')))

PRIVATE_DATA_DIR = Path(env('GIO_PRIVATE_DATA_DIR', str(PROJECT_ROOT / 'private_data')))
SISA_IMPORTS_DIR = PRIVATE_DATA_DIR / 'sisa_imports'
SISA_IMPORTS_PROCESADOS_DIR = SISA_IMPORTS_DIR / 'procesados'
SISA_EXPORTS_DIR = PRIVATE_DATA_DIR / 'sisa_exports'

EVIDENCIA_MAX_BYTES = env_int('GIO_EVIDENCIA_MAX_BYTES', 1024 * 1024)
EVIDENCIA_MAX_POR_FOLIO = env_int('GIO_EVIDENCIA_MAX_POR_FOLIO', 12)
DILACION_UMBRAL_DIAS = env_int('GIO_DILACION_UMBRAL_DIAS', 5)
DILACION_UMBRAL_CRITICO_DIAS = env_int('GIO_DILACION_UMBRAL_CRITICO_DIAS', 10)

DATA_UPLOAD_MAX_MEMORY_SIZE = env_int('GIO_DATA_UPLOAD_MAX_MEMORY_SIZE', 5 * 1024 * 1024)
FILE_UPLOAD_MAX_MEMORY_SIZE = DATA_UPLOAD_MAX_MEMORY_SIZE

EMAIL_BACKEND = env('GIO_EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend')

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_FILTER_BACKENDS': (
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ),
    'DEFAULT_PAGINATION_CLASS': 'gio_app.pagination.PaginacionGIO',
    'PAGE_SIZE': env_int('GIO_PAGE_SIZE', 50),
    'DEFAULT_THROTTLE_CLASSES': (
        'rest_framework.throttling.ScopedRateThrottle',
    ),
    'DEFAULT_THROTTLE_RATES': {
        'login': env('GIO_THROTTLE_LOGIN', '20/min'),
        'evidencia': env('GIO_THROTTLE_EVIDENCIA', '120/hour'),
    },
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=env_int('GIO_JWT_ACCESS_HORAS', 8)),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=env_int('GIO_JWT_REFRESH_DIAS', 1)),
    'ROTATE_REFRESH_TOKENS': True,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
}

if not DEBUG:
    SECURE_SSL_REDIRECT = env_bool('GIO_SECURE_SSL_REDIRECT', True)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = env_int('GIO_SECURE_HSTS_SECONDS', 31536000)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    X_FRAME_OPTIONS = 'DENY'

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'gio': {'format': '[{asctime}] {levelname} {name}: {message}', 'style': '{'},
    },
    'handlers': {
        'console': {'class': 'logging.StreamHandler', 'formatter': 'gio'},
    },
    'root': {'handlers': ['console'], 'level': env('GIO_LOG_LEVEL', 'INFO')},
    'loggers': {
        'django.db.backends': {'level': 'WARNING', 'handlers': ['console'], 'propagate': False},
    },
}
