from django.urls import path
from django.shortcuts import redirect
from . import views
from django.contrib.auth.views import LoginView, LogoutView

urlpatterns = [
    path('', lambda request: redirect('robot_dashboard')),
    path('top/', views.RobotDashboardView.as_view(), name='robot_dashboard'),
    path('robots/<str:unique_robot_id>/', views.RobotDetailView.as_view(), name='robot_detail'),
    path('signup/', views.SignupView.as_view(), name='signup'),
    path('login/', LoginView.as_view(template_name='login.html'), name='login'),
    path('logout/', LogoutView.as_view(next_page='login'), name='logout'),
    
    # API endpoints
    path('api/robots/', views.RobotListCreateAPIView.as_view(), name='robot_list_api'), 
    path('api/robots/<str:unique_robot_id>/', views.RobotDetailAPIView.as_view(), name='robot_detail_api'),
    path('api/robots/<str:unique_robot_id>/history/', views.RobotStateHistoryAPIView.as_view(), name='robot_state_history_api'),
]



