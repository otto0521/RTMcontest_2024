from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth import login
from django.shortcuts import render, redirect, get_object_or_404
from django.utils.safestring import mark_safe
from django.utils.timezone import localtime
from django.db.models import Max
from django.views.generic import DetailView, TemplateView, FormView
from django.urls import reverse_lazy
from rest_framework.permissions import IsAuthenticated
from rest_framework.generics import RetrieveUpdateDestroyAPIView, ListCreateAPIView, ListAPIView
from rest_framework.pagination import PageNumberPagination
from .models import Robot, RobotStateHistory
from .serializers import RobotSerializer, RobotStateHistorySerializer
import json


# ダッシュボード
class RobotDashboardView(LoginRequiredMixin, TemplateView):
    template_name = "robots.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        robots = Robot.objects.filter(owner=self.request.user)

        latest_timestamps = (
            RobotStateHistory.objects.filter(robot__in=robots)
            .values("robot_id")  
            .annotate(latest_timestamp=Max("timestamp")) 
        )

        latest_timestamps_map = {
            entry["robot_id"]: entry["latest_timestamp"]
            for entry in latest_timestamps
        }
        
        robots_json = [
            {
                "unique_robot_id": robot.unique_robot_id,
                "robot_id": robot.robot_id,
                "last_connected": localtime(robot.last_connected).strftime("%Y/%m/%d %H:%M:%S") if robot.last_connected else "Never",
            }
            for robot in robots
        ]

        for robot in robots:
            robot.latest_timestamp = (
                localtime(latest_timestamps_map.get(robot.id)).strftime("%Y/%m/%d %H:%M:%S")
                if latest_timestamps_map.get(robot.id)
                else "No Data"
            )

        context["robots"] = robots
        context["robots_json"] = mark_safe(json.dumps(robots_json))
        return context
    
# 詳細ページ
class RobotDetailView(DetailView):
    model = Robot
    template_name = 'robot_detail.html'
    context_object_name = 'robot'

    def get_object(self, queryset=None):
        unique_robot_id = self.kwargs.get('unique_robot_id')
        robot = get_object_or_404(Robot, unique_robot_id=unique_robot_id)

        # 最新のtimestampを取得
        latest_state = RobotStateHistory.objects.filter(robot=robot).aggregate(latest_timestamp=Max('timestamp'))
        robot.latest_timestamp = (
            localtime(latest_state['latest_timestamp']).strftime("%Y/%m/%d %H:%M:%S")
            if latest_state['latest_timestamp']
            else "No Data"
        )
        return robot

# サインアップ
class SignupView(FormView):
    template_name = "signup.html"
    form_class = UserCreationForm
    success_url = reverse_lazy('robot_dashboard')

    def form_valid(self, form):
        user = form.save()
        login(self.request, user)
        return super().form_valid(form)

# ロボットリスト取得, 新規作成
class RobotListCreateAPIView(ListCreateAPIView):

    queryset = Robot.objects.all()
    serializer_class = RobotSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Robot.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

# ロボット詳細取得、更新、削除
class RobotDetailAPIView(RetrieveUpdateDestroyAPIView):

    queryset = Robot.objects.all()
    serializer_class = RobotSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Robot.objects.filter(owner=self.request.user)

    def perform_update(self, serializer):
        serializer.save(owner=self.request.user)

#ロボット履歴取得
class RobotStateHistoryAPIView(ListAPIView):

    serializer_class = RobotStateHistorySerializer
    pagination_class = PageNumberPagination
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        unique_robot_id = self.kwargs['unique_robot_id']
        robot = Robot.objects.filter(unique_robot_id=unique_robot_id, owner=self.request.user).first()
        robot = get_object_or_404(Robot, unique_robot_id=unique_robot_id, owner=self.request.user)
        return RobotStateHistory.objects.filter(robot=robot)
