from pathlib import Path
import os
import environ
from django.utils.translation import gettext_lazy as _

# ベースディレクトリ
BASE_DIR = Path(__file__).resolve().parent.parent
PROJECT_NAME = os.path.basename(BASE_DIR)
LOCALE_PATHS = (os.path.join(BASE_DIR, "locale"),)

# 環境変数の読み込み
env = environ.Env(DEBUG=(bool, False))
environ.Env.read_env(os.path.join(BASE_DIR, ".env"))

# セキュリティ設定
SECRET_KEY = env("SECRET_KEY", default="dummy-secret-key")
DEBUG = env.bool("DEBUG", default=False)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

# アプリケーション定義
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "channels",
    "rest_framework",
    "api",
    "app",
]

# ミドルウェア設定
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# URL設定
ROOT_URLCONF = "app.urls"

# テンプレート設定
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": ["templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# ASGI & WSGIアプリケーション
WSGI_APPLICATION = "app.wsgi.application"
ASGI_APPLICATION = "app.asgi.application"


# チャンネルレイヤー (Redisバックエンド)
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [(env("REDIS_HOST", default="127.0.0.1"), int(env("REDIS_PORT", default=6379)))],
        },
    },
}

# RESTフレームワーク設定
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.BasicAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
}

# データベース設定
DATABASES = {
    "default": env.db("DATABASE_URL", default="sqlite:///db.sqlite3")
}

# パスワードバリデーション
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# ログイン関連設定
LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/top/"
LOGOUT_REDIRECT_URL = '/'

# ロケール設定
LANGUAGE_CODE = "ja"
LANGUAGES = [
    ("ja", _("日本語")),
    # ("en", _("English")),
]
TIME_ZONE = "Asia/Tokyo"
USE_I18N = True
USE_L10N = True
USE_TZ = True

# 静的ファイルとメディアファイルの設定
STATIC_URL = "/static/"
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, "static"),
]
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"
#MEDIA_URL = "/media/"
#MEDIA_ROOT = os.path.join(BASE_DIR, "media/")

# アップロード制限
DATA_UPLOAD_MAX_NUMBER_FIELDS = 20000
FILE_UPLOAD_MAX_MEMORY_SIZE = 15728640
DATA_UPLOAD_MAX_MEMORY_SIZE = 15728640

# ログ設定
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {  # 時間やレベルを記録
            "format": "{asctime} [{levelname}] {name} - {message}",
            "style": "{",
        },
        "simple": {  # シンプルな出力（コンソール向け）
            "format": "[{levelname}] {message}",
            "style": "{",
        },
    },
    "handlers": {
        "file": {
            "level": "DEBUG",  # すべてのログレベルを記録
            "class": "logging.FileHandler",
            "filename": os.path.join(BASE_DIR, "logs/all_logs.log"),
            "formatter": "verbose",  # 詳細フォーマットを適用
        },
        "console": {
            "level": "DEBUG",  # 開発中はすべてのログを表示
            "class": "logging.StreamHandler",
            "formatter": "simple",  # 簡易フォーマットを適用
        },
    },
    "loggers": {
        "django": {  # Djangoに関するログ
            "handlers": ["file", "console"],
            "level": 'WARNING',  # すべて記録
            "propagate": True,
        },
        "channels": {  # Channelsのログ
            "handlers": ["file", "console"],
            "level": 'WARNING',
            "propagate": True,
        },
        "app": {  # カスタムアプリ用のログ
            "handlers": ["file", "console"],
            "level": 'WARNING',  # すべて記録
            "propagate": True,
        },
        "": {  # ルートロガー（その他すべて）
            "handlers": ["file", "console"],
            "level": 'WARNING',
        },
    },
}


# セキュリティ設定（本番環境向け）
if not DEBUG:
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
