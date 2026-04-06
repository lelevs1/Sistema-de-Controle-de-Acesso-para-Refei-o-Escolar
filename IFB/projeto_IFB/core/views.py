import urllib.parse
import requests
import logging
from django.shortcuts import redirect
from django.utils import timezone
from django.conf import settings
from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from .models import User
from .permissions import IsAdmin

logger = logging.getLogger(__name__)

def test_api(request):
    return JsonResponse({"message": "API funcionando"})

# Registro de usuário (apenas admin)
@api_view(['POST'])
@permission_classes([IsAdmin])
def register_user(request):
    data = request.data
    required = ['email', 'nome', 'papel']
    if not all(k in data for k in required):
        return Response({'error': 'Dados obrigatórios: email, nome, papel'}, status=400)
    if User.objects.filter(email=data['email']).exists():
        return Response({'error': 'Usuário já existe'}, status=400)
    user = User.objects.create_user(
        email=data['email'],
        nome=data['nome'],
        password=data.get('password'),  # opcional para OAuth
        papel=data['papel']
    )
    return Response({'message': 'Usuário criado com sucesso'})

# Login tradicional (apenas operador, empresa, gestor)
@api_view(['POST'])
def login(request):
    email = request.data.get('email')
    password = request.data.get('password')
    if not email or not password:
        return Response({'error': 'Email e senha obrigatórios'}, status=400)

    user = User.objects.filter(email=email).first()
    if not user or not user.check_password(password):
        return Response({'error': 'Credenciais inválidas'}, status=401)

    # Bloqueia login por senha para fiscais e admin
    if user.papel in ['fiscal', 'admin']:
        return Response({'error': 'Este usuário deve usar login com Google'}, status=403)

    if not user.is_active:
        return Response({'error': 'Usuário desativado'}, status=403)

    user.ultimo_acesso = timezone.now()
    user.save()

    refresh = RefreshToken.for_user(user)
    return Response({
        'refresh': str(refresh),
        'access': str(refresh.access_token),
        'papel': user.papel,
        'email': user.email
    })

# Inicia fluxo OAuth Google
def google_login(request):
    base_url = "https://accounts.google.com/o/oauth2/v2/auth"
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "select_account",
    }
    url = f"{base_url}?{urllib.parse.urlencode(params)}"
    return redirect(url)

# Callback do Google
def google_callback(request):
    code = request.GET.get('code')
    if not code:
        return redirect("http://localhost:5173/login?error=missing_code")

    token_url = "https://oauth2.googleapis.com/token"
    data = {
        "code": code,
        "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "grant_type": "authorization_code",
    }
    try:
        token_response = requests.post(token_url, data=data, timeout=10)
        token_response.raise_for_status()
        token_data = token_response.json()
    except Exception as e:
        logger.error(f"Erro no token: {e}")
        return redirect("http://localhost:5173/login?error=token_failed")

    access_token = token_data.get("access_token")
    if not access_token:
        return redirect("http://localhost:5173/login?error=no_token")

    try:
        user_info = requests.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10
        ).json()
    except Exception as e:
        logger.error(f"Erro ao obter userinfo: {e}")
        return redirect("http://localhost:5173/login?error=userinfo_failed")

    email = user_info.get("email")
    if not email:
        return redirect("http://localhost:5173/login?error=no_email")

    # Restrição de domínio para fiscais e admin
    allowed_domains = ["escola.gov.br", "educacao.gov.br"]
    domain = email.split("@")[-1]
    if domain not in allowed_domains:
        return redirect("http://localhost:5173/login?error=domain_not_allowed")

    # Busca ou cria usuário
    user = User.objects.filter(email=email).first()
    if not user:
        # Cria como fiscal (padrão), admin pode ser promovido depois
        user = User.objects.create_user(
            email=email,
            nome=user_info.get('name', email.split('@')[0]),
            papel='fiscal',
            password=None
        )
        user.google_id = user_info.get('id')
        user.save()
    else:
        # Se já existe, mas papel não é fiscal/admin, bloqueia
        if user.papel not in ['fiscal', 'admin']:
            return redirect("http://localhost:5173/login?error=unauthorized")
        if not user.google_id:
            user.google_id = user_info.get('id')
            user.save()

    user.ultimo_acesso = timezone.now()
    user.save()

    refresh = RefreshToken.for_user(user)
    access_jwt = str(refresh.access_token)
    refresh_jwt = str(refresh)

    # Redireciona para o frontend com tokens
    frontend_url = f"http://localhost:5173/dashboard?access={access_jwt}&refresh={refresh_jwt}&papel={user.papel}"
    return redirect(frontend_url)

# Logout (invalida o refresh token - opcional)
@api_view(['POST'])
def logout(request):
    try:
        refresh_token = request.data.get('refresh')
        if refresh_token:
            token = RefreshToken(refresh_token)
            token.blacklist()  # requer 'rest_framework_simplejwt.token_blacklist' no INSTALLED_APPS
        return Response({'message': 'Logout realizado com sucesso'})
    except TokenError:
        return Response({'error': 'Token inválido'}, status=400)

# Perfil do usuário
@api_view(['GET'])
def perfil_usuario(request):
    if not request.user.is_authenticated:
        return Response({'error': 'Não autenticado'}, status=401)
    return Response({
        'email': request.user.email,
        'nome': request.user.nome,
        'papel': request.user.papel,
        'ultimo_acesso': request.user.ultimo_acesso,
    })