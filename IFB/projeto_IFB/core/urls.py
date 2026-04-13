# core/urls.py (versão limpa)
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView
from . import views
from .views import StudentViewSet

router = DefaultRouter()
router.register(r'estudantes', StudentViewSet, basename='estudante')

urlpatterns = [
    path('api/test/', views.test_api),
    path('api/login/', views.login, name='login'),
    path('api/register/', views.register_user, name='register'),
    path('api/logout/', views.logout, name='logout'),
    path('api/perfil/', views.perfil_usuario, name='perfil'),
    path('auth/google/', views.google_login, name='google-login'),
    path('auth/google/callback/', views.google_callback, name='google-callback'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('', views.home, name='home'),
    path('api/', include(router.urls)),
]