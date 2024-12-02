from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
from django.utils.timezone import now
from django.db import transaction
from .models import Robot, RobotStateHistory
from django.contrib.auth.models import User
import time
import json
import asyncio
import logging

# ロギング設定（必要に応じて）
logger = logging.getLogger(__name__)

class RobotStateConsumer(AsyncWebsocketConsumer):
    robot_data_cache = {}  # { unique_robot_id: [データキャッシュリスト] }
    batch_size = 10  # バッチサイズ
    flush_interval = 60  # フラッシュ間隔（秒）
    max_cache_size = 100  # キャッシュの最大サイズ
    ping_interval = 30  # サーバーからpingを送信する間隔（秒）
    pong_timeout = 10  # クライアントがpongを返さなかった場合に切断するまでのタイムアウト（秒）

    async def connect(self):
        # クエリパラメータの取得
        query_string = self.scope.get("query_string", b"").decode("utf-8")
        params = dict(param.split("=") for param in query_string.split("&") if "=" in param)
        self.unique_robot_id = params.get("unique_robot_id")

        if not self.unique_robot_id:
            await self.close(code=4001)
            logger.error("Connection refused: Missing unique_robot_id")
            return

        try:
            await self.create_robot_if_not_exists(
                unique_robot_id=self.unique_robot_id,
                robot_id=params.get("robot_id", "unknown"),
                owner=params.get("owner", "unknown")
            )
        except Exception as e:
            logger.error(f"Error during robot creation: {e}")
            await self.close(code=4002)
            return

        self.robot_data = {}
        self.group_name = f"robot_states_{self.unique_robot_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        logger.info(f"WebSocket connected: {self.channel_name}, Unique Robot ID: {self.unique_robot_id}")

        # キャッシュ初期化
        if self.unique_robot_id not in self.robot_data_cache:
            self.robot_data_cache[self.unique_robot_id] = []

        # キャッシュフラッシュタスクの開始
        self.flush_task = asyncio.create_task(self.flush_data_cache(self.unique_robot_id))

        # Ping-Pongタスクの開始
        self.ping_task = asyncio.create_task(self.ping_pong_monitor())

    async def disconnect(self, close_code):
        if self.unique_robot_id:
            try:
                # チャネルグループから削除
                await self.channel_layer.group_discard(self.group_name, self.channel_name)
                logger.info(f"WebSocket disconnected: {self.channel_name}, Unique Robot ID: {self.unique_robot_id}")
                
                # フラッシュタスクのキャンセル
                if hasattr(self, "flush_task"):
                    self.flush_task.cancel()
                    try:
                        await self.flush_task
                    except asyncio.CancelledError:
                        logger.info(f"Flush task for {self.unique_robot_id} cancelled successfully.")
                
                # Ping-Pongタスクのキャンセル
                if hasattr(self, "ping_task"):
                    self.ping_task.cancel()
                    try:
                        await self.ping_task
                    except asyncio.CancelledError:
                        logger.info(f"Ping-Pong task for {self.unique_robot_id} cancelled successfully.")
                
                # データベースへの最終的なデータフラッシュ
                await self.flush_to_db(self.unique_robot_id, force=True)
            except Exception as e:
                logger.error(f"Error during disconnect: {e}")
        else:
            logger.error("Disconnect called without a valid unique_robot_id.")

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            if "robot_id" in data and "state" in data and "owner" in data:
                self.robot_data.update(data)
                await self.update_robot_info(data)

                # 受け取ったstateデータをデバッグ
                logger.info(f"Received state data for robot {data['robot_id']}: {data['state']}")

                # キャッシュにデータを追加
                self.append_to_cache(self.unique_robot_id, {
                    "robot_id": data["robot_id"],
                    "state": data["state"],  # stateはそのまま辞書型で保存
                    "timestamp": now(),
                })

                await self.broadcast_to_frontend({
                    "message": "New data received",
                    "unique_robot_id": self.unique_robot_id,
                    "robot_id": data["robot_id"],
                    "state": data["state"]  # 辞書型のstateをそのまま送信
                })
            elif "pong" in data:
                # クライアントからpongが送られた場合
                self.last_pong_time = time.time()  # pong受信時にタイマーをリセット
            else:
                logger.error("Invalid data received: Missing 'robot_id', 'state', or 'owner'")
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding JSON: {e}")
            await self.broadcast_to_frontend({"message": "Error decoding JSON", "error": str(e)})
        except Exception as e:
            logger.error(f"Error processing WebSocket data: {e}")

    def append_to_cache(self, unique_robot_id, data):
        cache = self.robot_data_cache.get(unique_robot_id, [])
        cache.append(data)
        if len(cache) > self.max_cache_size:
            cache.pop(0)
        self.robot_data_cache[unique_robot_id] = cache

    async def broadcast_to_frontend(self, data):
        await self.channel_layer.group_send(
            self.group_name,
            {
                "type": "send_to_client",
                "data": {
                    "status": "success" if "error" not in data else "error",
                    **data,
                },
            }
        )

    async def send_to_client(self, event):
        await self.send(text_data=json.dumps(event["data"]))

    async def create_robot_if_not_exists(self, unique_robot_id, robot_id, owner):
        @sync_to_async
        def create_robot():
            # ユーザーが存在しない場合は 'unknown' を設定
            owner_instance, _ = User.objects.get_or_create(username=owner if owner else "unknown")
            robot, created = Robot.objects.get_or_create(
                unique_robot_id=unique_robot_id,
                defaults={
                    "robot_id": robot_id,
                    "owner": owner_instance,
                    "last_connected": now()
                }
            )
            return robot, created
                
        robot, created = await create_robot()
        logger.info(f"Robot created in DB: {await sync_to_async(str)(robot)}" if created else f"Robot already exists in DB: {await sync_to_async(str)(robot)}")

    async def update_robot_info(self, data):
        @sync_to_async
        def update_or_create_robot():
            # ユーザーが存在しない場合は 'unknown' を設定
            owner_instance, _ = User.objects.get_or_create(username=data.get("owner", "unknown"))
            robot, created = Robot.objects.get_or_create(
                unique_robot_id=self.unique_robot_id,
                defaults={
                    "robot_id": data.get("robot_id", "unknown"),
                    "owner": owner_instance,
                    "last_connected": now(),
                },
            )
            updated = False
            if not created:
                if robot.robot_id != data["robot_id"]:
                    robot.robot_id = data["robot_id"]
                    updated = True
                if robot.owner != owner_instance:
                    robot.owner = owner_instance
                    updated = True
                if updated:
                    robot.last_connected = now()
                    robot.save()
            return robot, updated

        robot, updated = await update_or_create_robot()
        if updated:
            # 更新後にページリロード指示をフロントエンドに送信
            await self.broadcast_to_frontend({
                "reload": True,  # ページリロードの指示
            })
        logger.info(f"Robot info updated: {robot}" if updated else f"Robot info unchanged: {robot}")

    async def flush_data_cache(self, unique_robot_id):
        try:
            while True:
                await asyncio.sleep(self.flush_interval)
                await self.flush_to_db(unique_robot_id)
        except asyncio.CancelledError:
            await self.flush_to_db(unique_robot_id, force=True)

    @sync_to_async
    def flush_to_db(self, unique_robot_id, force=False):
        cache = self.robot_data_cache.get(unique_robot_id, [])
        if not cache and not force:
            return

        with transaction.atomic():
            for data in cache:
                RobotStateHistory.objects.create(
                    robot=Robot.objects.get(unique_robot_id=unique_robot_id),
                    state=data["state"],
                    timestamp=data["timestamp"]
                )
            # キャッシュをクリア
            self.robot_data_cache[unique_robot_id] = []
        logger.info(f"Flushed {len(cache)} records to DB for robot {unique_robot_id}")

    async def ping_pong_monitor(self):
        while True:
            if hasattr(self, 'last_pong_time') and time.time() - self.last_pong_time > self.pong_timeout:
                logger.warning("Pong timeout exceeded. Closing connection.")
                await self.close()
                break
            await asyncio.sleep(self.ping_interval)
            await self.send(text_data=json.dumps({"ping": "ping"}))
