import os
import logging
import asyncio
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack

# ログ設定
logger = logging.getLogger("django")

# Django 設定モジュールを指定
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "app.settings")

# 遅延インポートを利用するための関数
def get_websocket_urlpatterns():
    from api.routing import websocket_urlpatterns
    return websocket_urlpatterns

# Lifespan handler for startup and shutdown events
async def lifespan(scope, receive, send):
    if scope["type"] == "lifespan":
        tasks = []  # 追跡するタスクのリスト
        try:
            while True:
                message = await receive()
                if message["type"] == "lifespan.startup":
                    logger.info("ASGI server starting up.")
                    await send({"type": "lifespan.startup.complete"})
                elif message["type"] == "lifespan.shutdown":
                    logger.info("ASGI server shutting down. Cancelling tasks.")
                    # タスクのキャンセル処理
                    for task in tasks:
                        task.cancel()
                    await asyncio.gather(*tasks, return_exceptions=True)
                    await send({"type": "lifespan.shutdown.complete"})
                    break
        except Exception as e:
            logger.error(f"Lifespan error: {e}", exc_info=True)
            await send({"type": "lifespan.shutdown.complete"})

try:
    application = ProtocolTypeRouter({
        "http": get_asgi_application(),  # HTTP プロトコル用
        "websocket": AuthMiddlewareStack(  # WebSocket プロトコル用
            URLRouter(
                get_websocket_urlpatterns()  # 遅延ロード
            )
        ),
        "lifespan": lifespan,  # Lifespan プロトコルを追加
    })
except Exception as e:
    logger.exception("ASGI application initialization error")  # スタックトレースを含む
    raise
