from django.urls import path
from . import views
from django.contrib.auth.views import LoginView

urlpatterns = [
    path('top/', views.robot_dashboard, name='robot_dashboard'),
    path('signup/', views.signup, name='signup'),
    path('login/', LoginView.as_view(template_name='login.html'), name='login'),
    path('logout/', views.logout_view, name='logout'),
    
    # API endpoints
    path('api/robots/', views.robot_list, name='robot_list'),
    path('api/robots/<str:unique_robot_id>/', views.robot_detail, name='robot_detail'),
    path('api/robots/<str:unique_robot_id>/history/', views.robot_state_history, name='robot_state_history'),
]



