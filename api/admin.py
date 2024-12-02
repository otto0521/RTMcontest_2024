from django.contrib import admin
from .models import Robot, RobotStateHistory

@admin.register(Robot)
class RobotAdmin(admin.ModelAdmin):
    list_display = ('unique_robot_id', 'robot_id', 'owner', 'last_connected')
    search_fields = ('robot_id', 'owner__username')

@admin.register(RobotStateHistory)
class RobotStateHistoryAdmin(admin.ModelAdmin):
    list_display = ('robot', 'timestamp')
    search_fields = ('robot__unique_robot_id', 'robot__robot_id')
    list_filter = ('timestamp',)
