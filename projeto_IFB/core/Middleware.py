from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from django.http import JsonResponse
import re

class JWTAuthenticationMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        auth = JWTAuthentication()
        try:
            user_auth = auth.authenticate(request)
            if user_auth:
                request.user, _ = user_auth
        except (InvalidToken, TokenError):
            pass
        return self.get_response(request)

class RoleAuthorizationMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Protege rotas /api/admin/*
        if re.match(r'^/api/admin/.*', request.path):
            if not request.user.is_authenticated or request.user.papel != 'admin':
                return JsonResponse({'error': 'Acesso negado: admin necessário'}, status=403)

        # Protege rotas /api/fiscal/*
        if re.match(r'^/api/fiscal/.*', request.path):
            if not request.user.is_authenticated or request.user.papel not in ['fiscal', 'admin']:
                return JsonResponse({'error': 'Acesso negado: fiscal ou admin necessário'}, status=403)

        return self.get_response(request)