from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
from channels.layers import get_channel_layer
from django.utils.timezone import now
from django.db import transaction
from .models import Robot, RobotStateHistory
from django.contrib.auth.models import User
import time
import json
import asyncio
import logging

# ロギング設定
logger = logging.getLogger(__name__)
connected_robots = set()

# グローバルキャッシュ
shared_robot_cache = {}  # { unique_robot_id: [データキャッシュリスト] }
shared_frontend_data_buffer = {}  # フロントエンド更新用キャッシュ

class RobotStateConsumer(AsyncWebsocketConsumer):
    # WebSocket関連設定
    frontend_update_interval = 1  # フロントエンド更新間隔（秒）
    flush_interval = 10  # DBフラッシュ間隔（秒）
    robot_connection_times = {}  # { unique_robot_id: 接続開始時刻 }
    max_cache_size = 100  # キャッシュの最大サイズ
    ping_interval = 60  # サーバーからpingを送信する間隔（秒）
    pong_timeout = 10  # クライアントがpongを返さなかった場合に切断するまでのタイムアウト（秒）

    async def connect(self):
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
                robot_id="unknown",
                owner="unknown"
            )
            
        except Exception as e:
            logger.error(f"Error during robot creation: {e}")
            await self.close(code=4002)
            return

        await self.channel_layer.group_add("robot_states", self.channel_name)
        await self.accept()

        self.robot_connection_times[self.unique_robot_id] = time.time()

        # キャッシュ初期化
        shared_robot_cache.setdefault(self.unique_robot_id, [])
        shared_frontend_data_buffer.setdefault(self.unique_robot_id, {})

        connected_robots.add(self.unique_robot_id)
        logger.info(f"Robot {self.unique_robot_id} connected. Currently connected robots: {len(connected_robots)}")

    async def disconnect(self, close_code):
        if self.unique_robot_id:
            try:
                await self.channel_layer.group_discard("robot_states", self.channel_name)
                connected_robots.discard(self.unique_robot_id)

                logger.info(f"Robot {self.unique_robot_id} disconnected. Remaining connections: {len(connected_robots)}")
            except Exception as e:
                logger.error(f"Error during disconnect: {e}")

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            if "robot_id" in data and "state" in data and "owner" in data:

                await self.update_robot_info(
                    unique_robot_id = self.unique_robot_id,
                    robot_id = data["robot_id"],
                    owner = data["owner"]
                )
                 
                connection_time = int(time.time() - self.robot_connection_times[self.unique_robot_id])
                formatted_connection_time = f"{connection_time // 3600:02}:{(connection_time % 3600) // 60:02}:{connection_time % 60:02}"

                # キャッシュにデータを追加
                shared_robot_cache[self.unique_robot_id].append({
                    "robot_id": data["robot_id"],
                    "state": data["state"],
                    "timestamp": now(),
                })

                # キャッシュサイズ制限の確認
                if len(shared_robot_cache[self.unique_robot_id]) > self.max_cache_size:
                    logger.warning(f"Cache size exceeded for {self.unique_robot_id}. Flushing immediately.")
                    await self.flush_cache_to_db(self.unique_robot_id)

                # フロントエンド用の更新データをキャッシュ
                shared_frontend_data_buffer[self.unique_robot_id] = {
                    "unique_robot_id": self.unique_robot_id,
                    "robot_id": data["robot_id"],
                    "owner": data["owner"],
                    "state": json.dumps(data["state"]) if isinstance(data["state"], dict) else data["state"],
                    "connection_time": formatted_connection_time,
                    "timestamp": now().isoformat(),
                }

            elif "pong" in data:
                # クライアントからpongが送られた場合
                self.last_pong_time = time.time()
            else:
                logger.error("Invalid data received: Missing 'robot_id' or 'state'")
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding JSON: {e}")
        except Exception as e:
            logger.error(f"Error processing WebSocket data: {e}")

    @sync_to_async
    def create_robot_if_not_exists(self, unique_robot_id, robot_id, owner):

        owner_instance, _ = User.objects.get_or_create(username=owner if owner else "unknown")
        Robot.objects.get_or_create(
            unique_robot_id=unique_robot_id,
            defaults={"robot_id": robot_id, "owner": owner_instance, "last_connected": now()}
        )
    
    @sync_to_async
    def update_robot_info(self, unique_robot_id, robot_id, owner):
        try:
            robot = Robot.objects.get(unique_robot_id=unique_robot_id)
            updated = False

            if robot.robot_id == "unknown" and robot_id != "unknown":
                robot.robot_id = robot_id
                updated = True

            if robot.owner.username == "unknown" and owner != "unknown":
                try:
                    owner_instance = User.objects.get(username=owner)
                    robot.owner = owner_instance
                    updated = True
                except User.DoesNotExist:
                    logger.info(f"Owner '{owner}' does not exist. Skipping update for robot {unique_robot_id}.")
            if updated:
                robot.save()
                logger.info(f"Robot {unique_robot_id} updated: robot_id={robot.robot_id}, owner={robot.owner.username}")
            else:
                logger.info(f"No update needed for robot {unique_robot_id}.")

        except Robot.DoesNotExist:
            logger.info(f"Robot with unique_robot_id {unique_robot_id} does not exist. Skipping update.")
        except Exception as e:
            logger.info(f"Error updating robot info: {e}")

class SharedTasks:
    @staticmethod
    async def flush_to_db():
        while True:
            await asyncio.sleep(10)  # 10秒間隔で実行
            try:
                # キャッシュが空ならスキップ
                if not any(shared_robot_cache.values()):
                    #logger.debug("No data in cache to flush to DB. Skipping...")
                    continue

                # ORM 操作を非同期対応に
                await sync_to_async(SharedTasks._flush_to_db_sync)()
                logger.info("Flushed data to DB.")
            except Exception as e:
                logger.error(f"Error flushing to DB: {e}")

    @staticmethod
    def _flush_to_db_sync():
        # ORM の操作は同期で実行
        with transaction.atomic():
            for unique_robot_id, cache in list(shared_robot_cache.items()):
                if cache:  # キャッシュが空の場合はスキップ
                    RobotStateHistory.objects.bulk_create([
                        RobotStateHistory(
                            robot=Robot.objects.get(unique_robot_id=unique_robot_id),
                            state=data["state"],
                            timestamp=data["timestamp"]
                        )
                        for data in cache
                    ])
                    shared_robot_cache[unique_robot_id] = []  # キャッシュをクリア

    @staticmethod
    async def send_to_frontend(channel_layer):
        while True:
            await asyncio.sleep(1)  # 1秒間隔で実行
            try:
                # フロントエンドバッファが空ならスキップ
                if not shared_frontend_data_buffer:
                    #logger.debug("No data in frontend buffer to send. Skipping...")
                    continue

                logger.debug(f"Sending to frontend: {shared_frontend_data_buffer}")
                await channel_layer.group_send(
                    "frontend_updates",
                    {
                        "type": "send_to_client",
                        "data": list(shared_frontend_data_buffer.values()),
                    },
                )
                shared_frontend_data_buffer.clear()  # フロントエンドバッファをクリア
            except Exception as e:
                logger.error(f"Error sending to frontend: {e}")


class FrontendConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.group_name = "frontend_updates"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()
        logger.info(f"Frontend WebSocket connected: {self.channel_name}")

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)
        logger.info(f"Frontend WebSocket disconnected: {self.channel_name}")

    async def send_to_client(self, event):
        try:
            await self.send(text_data=json.dumps(event["data"]))
        except Exception as e:
            logger.error(f"Error sending data to frontend: {e}")

# サーバー起動時にタスクを開始
async def start_tasks(channel_layer):
    logger.info("start_tasks called with channel_layer: %s", channel_layer)
    asyncio.create_task(SharedTasks.flush_to_db())
    asyncio.create_task(SharedTasks.send_to_frontend(channel_layer))
