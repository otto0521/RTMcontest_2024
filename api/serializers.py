from rest_framework import serializers
from .models import Robot, RobotStateHistory

# RobotSerializer
class RobotSerializer(serializers.ModelSerializer):
    owner = serializers.StringRelatedField()  # owner.username を表示する

    class Meta:
        model = Robot
        fields = ['unique_robot_id', 'robot_id', 'owner', 'last_connected']

    def validate(self, data):
        if not data.get('robot_id'):
            raise serializers.ValidationError("robot_id は必須です。")
        if not data.get('owner'):
            raise serializers.ValidationError("owner は必須です。")
        return data

# RobotStateHistorySerializer
class RobotStateHistorySerializer(serializers.ModelSerializer):
    robot = serializers.StringRelatedField()  # robot.robot_id を表示する

    class Meta:
        model = RobotStateHistory
        fields = ['robot', 'state', 'timestamp']
