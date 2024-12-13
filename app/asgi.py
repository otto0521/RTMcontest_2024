import os
import logging
import asyncio
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from channels.layers import get_channel_layer

# ログ設定
logger = logging.getLogger("django")

# Django 設定モジュール指定
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "app.settings")

# 遅延インポート関数
def get_websocket_urlpatterns():
    from api.routing import websocket_urlpatterns
    return websocket_urlpatterns

def get_start_tasks():
    from api.consumers import start_tasks
    return start_tasks

# Lifespan handler for startup and shutdown events
async def lifespan(scope, receive, send):
    if scope["type"] == "lifespan":
        tasks = []
        try:
            while True:
                message = await receive()
                if message["type"] == "lifespan.startup":
                    logger.info("ASGI server starting up.")

                    # start_tasks を取得し、channel_layer を渡す
                    start_tasks = get_start_tasks()
                    channel_layer = get_channel_layer()
                    tasks.append(asyncio.create_task(start_tasks(channel_layer)))

                    await send({"type": "lifespan.startup.complete"})
                elif message["type"] == "lifespan.shutdown":
                    logger.info("ASGI server shutting down. Cancelling tasks.")
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
        "http": get_asgi_application(),
        "websocket": AuthMiddlewareStack(
            URLRouter(
                get_websocket_urlpatterns()
            )
        ),
        "lifespan": lifespan,
    })
except Exception as e:
    logger.exception("ASGI application initialization error")
    raise
