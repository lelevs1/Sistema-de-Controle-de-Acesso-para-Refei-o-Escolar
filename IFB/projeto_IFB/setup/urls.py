from django.contrib import admin
from django.urls import path
from core import views
from rest_framework_simplejwt.views import TokenRefreshView
urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/test/', views.test_api),
    path('api/login/', views.login, name='login'),
    path('api/register/', views.register_user, name='register'),
    path('api/logout/', views.logout, name='logout'),
    path('api/perfil/', views.perfil_usuario, name='perfil'),
    path('auth/google/', views.google_login, name='google-login'),
    path('auth/google/callback/', views.google_callback, name='google-callback'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh')
]