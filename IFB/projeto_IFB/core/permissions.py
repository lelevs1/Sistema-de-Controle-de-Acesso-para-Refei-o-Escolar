from rest_framework.permissions import BasePermission

class IsAdmin(BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.papel == 'admin'

class IsAdminOrFiscal(BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.papel in ['admin', 'fiscal']

class IsAdminOrGestor(BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.papel in ['admin', 'gestor']

class IsFiscal(BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.papel in ['fiscal', 'admin']

class IsAdminOrFiscalOrGestor(BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.papel in ['admin', 'fiscal', 'gestor']

# ========== NOVAS CLASSES (adicione exatamente isso) ==========
class IsAdminOrFiscalOrEmpresa(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.papel in ['admin', 'fiscal', 'empresa']

class IsAdminOrFiscalOrOperador(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.papel in ['admin', 'fiscal', 'operador']