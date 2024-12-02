from django.db import models
from django.contrib.auth.models import User

class Robot(models.Model):
    unique_robot_id = models.CharField(max_length=255, unique=True, db_index=True)  # ロボットUUID
    robot_id = models.CharField(max_length=255)  # ユーザー指定ロボットID
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="robots")  # 所有者
    last_connected = models.DateTimeField(auto_now=True)  # 最終接続時刻

    def __str__(self):
        return f"{self.robot_id} ({self.owner.username})"

class RobotStateHistory(models.Model):
    robot = models.ForeignKey(Robot, on_delete=models.CASCADE, related_name="state_histories")  # ロボットとの関連
    state = models.JSONField()  # 状態データをJSON形式で保存
    timestamp = models.DateTimeField(db_index=True)  # 状態が送信された時刻

    def __str__(self):
        return f"{self.robot.robot_id} at {self.timestamp}"

    class Meta:
        ordering = ["-timestamp"]
