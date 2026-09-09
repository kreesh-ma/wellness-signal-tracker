from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('api/readings/', views.get_readings, name='get_readings'),
    path('api/latest/', views.get_latest, name='get_latest'),
    path('api/analyze/', views.analyze_frame, name='analyze_frame'),
    path('api/history/', views.get_history, name='get_history'),
]
