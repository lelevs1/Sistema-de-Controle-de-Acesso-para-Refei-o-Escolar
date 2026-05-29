from rest_framework.permissions import BasePermission

class IsAdmin(BasePermission):
    """Permite acesso apenas para usuários com papel 'admin'."""
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.papel == 'admin'

class IsAdminOrFiscal(BasePermission):
    """Permite acesso para usuários com papel 'admin' ou 'fiscal'."""
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.papel in ['admin', 'fiscal']

class IsAdminOrGestor(BasePermission):
    """Permite acesso para usuários com papel 'admin' ou 'gestor'."""
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.papel in ['admin', 'gestor']

class IsFiscal(BasePermission):
    """Permite acesso para usuários com papel 'fiscal' (e admin)."""
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.papel in ['fiscal', 'admin']

class IsAdminOrFiscalOrGestor(BasePermission):
    """Permite acesso para usuários com papel 'admin', 'fiscal' ou 'gestor'."""
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.papel in ['admin', 'fiscal', 'gestor']