from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login, logout
from django.shortcuts import render, redirect
from django.utils.safestring import mark_safe
from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from .models import Robot, RobotStateHistory
from .serializers import RobotSerializer, RobotStateHistorySerializer
import json

# サインアップ
def signup(request):
    """
    新しいユーザーを登録するビュー
    """
    if request.method == "POST":
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('robot_dashboard')
    else:
        form = UserCreationForm()
    return render(request, "signup.html", {"form": form})


# ログイン後のダッシュボード
@login_required
def robot_dashboard(request):
    """
    ログイン後のロボットダッシュボード
    """
    robots = Robot.objects.filter(owner=request.user)
    robots_json = mark_safe(json.dumps([  # 初期状態を"Non-connect"に設定
        {
            "unique_robot_id": robot.unique_robot_id,
            "robot_id": robot.robot_id,
            "owner": robot.owner.username,
            "last_connected": robot.last_connected.isoformat(),
            "state": "Non-connect",  # 状態のデフォルト値
        }
        for robot in robots
    ]))
    return render(request, "robots.html", {"robots": robots, "robots_json": robots_json})


# ログアウト
@login_required
def logout_view(request):
    """
    ログアウト後のリダイレクト
    """
    logout(request)
    return redirect('login')


# ロボットリスト取得および新規作成
@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def robot_list(request):
    """
    ロボットのリスト取得（GET）または新規作成（POST）
    """
    if request.method == 'GET':
        robots = Robot.objects.filter(owner=request.user)
        serializer = RobotSerializer(robots, many=True)
        return Response(serializer.data)

    elif request.method == 'POST':
        data = request.data.copy()
        data['owner'] = request.user.id  # ユーザーIDを直接設定
        serializer = RobotSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ロボット詳細取得、更新、削除
@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
def robot_detail(request, unique_robot_id):
    """
    指定されたロボットの詳細を取得、更新、または削除
    """
    try:
        robot = Robot.objects.get(unique_robot_id=unique_robot_id, owner=request.user)
    except Robot.DoesNotExist:
        return Response({"error": "Robot not found or access denied."}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        serializer = RobotSerializer(robot)
        return Response(serializer.data)

    elif request.method == 'PUT':
        data = request.data.copy()
        data['owner'] = request.user.id  # ユーザーIDを直接設定
        serializer = RobotSerializer(robot, data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    elif request.method == 'DELETE':
        robot.delete()
        return Response({"message": "Robot deleted successfully."}, status=status.HTTP_200_OK)


# ロボットの状態履歴取得
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def robot_state_history(request, unique_robot_id):
    """
    指定されたロボットの状態履歴を取得
    """
    try:
        robot = Robot.objects.get(unique_robot_id=unique_robot_id, owner=request.user)
    except Robot.DoesNotExist:
        return Response({"error": "Robot not found or access denied."}, status=status.HTTP_404_NOT_FOUND)

    histories = RobotStateHistory.objects.filter(robot=robot)

    # ページネーション
    paginator = PageNumberPagination()
    paginated_histories = paginator.paginate_queryset(histories, request)
    serializer = RobotStateHistorySerializer(paginated_histories, many=True)
    return paginator.get_paginated_response(serializer.data)
