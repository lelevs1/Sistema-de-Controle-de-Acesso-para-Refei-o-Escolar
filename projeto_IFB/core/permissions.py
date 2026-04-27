from rest_framework.permissions import BasePermission

class IsAdmin(BasePermission):
    """Permite acesso apenas para usuários com papel 'admin'."""
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.papel == 'admin'

class IsAdminOrFiscal(BasePermission):
    """Permite acesso para usuários com papel 'admin' ou 'fiscal'."""
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.papel in ['admin', 'fiscal']