from django.contrib import admin
from .models import Student, Turma, Digital, Almoco, LogLiberacao, User
from .models import Curso

@admin.register(Curso)
class CursoAdmin(admin.ModelAdmin):
    list_display = ('nome',)
    search_fields = ('nome',)
# ==================== PERSONALIZAÇÃO GLOBAL DO ADMIN ====================
admin.site.site_header = "Sistema de Gestão de Almoço - IFB"
admin.site.site_title = "Painel de Controle"
admin.site.index_title = "Bem-vindo(a) ao Sistema"

# ==================== STUDENT ====================
@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('id', 'nome', 'matricula', 'curso', 'turma', 'ativo', 'data_nascimento')
    search_fields = ('nome', 'matricula')
    list_filter = ('curso', 'turma', 'ativo')
    list_editable = ('ativo',)  # permite editar o status ativo/inativo diretamente na lista
    list_display_links = ('nome',)
    ordering = ('nome',)

# ==================== TURMA ====================
@admin.register(Turma)
class TurmaAdmin(admin.ModelAdmin):
    list_display = ('nome', 'turno')
    search_fields = ('nome',)

# ==================== DIGITAL ====================
@admin.register(Digital)
class DigitalAdmin(admin.ModelAdmin):
    list_display = ('id', 'estudante', 'dedo', 'codigo_hex_resumido', 'created_at')
    search_fields = ('estudante__nome', 'codigo_hex')
    list_filter = ('dedo',)
    readonly_fields = ('created_at',)

    def codigo_hex_resumido(self, obj):
        return f"{obj.codigo_hex[:20]}..." if obj.codigo_hex else "-"
    codigo_hex_resumido.short_description = "Código HEX (resumo)"

# ==================== ALMOÇO ====================
@admin.register(Almoco)
class AlmocoAdmin(admin.ModelAdmin):
    list_display = ('id', 'estudante', 'data_hora', 'metodo', 'operador')
    search_fields = ('estudante__nome',)
    list_filter = ('metodo', 'data_hora')
    date_hierarchy = 'data_hora'
    readonly_fields = ('data_hora',)

# ==================== LOG DE LIBERAÇÃO ====================
@admin.register(LogLiberacao)
class LogLiberacaoAdmin(admin.ModelAdmin):
    list_display = ('id', 'estudante', 'tipo', 'data_hora', 'operador')
    search_fields = ('estudante__nome',)
    list_filter = ('tipo', 'data_hora')
    date_hierarchy = 'data_hora'
    readonly_fields = ('data_hora',)

# ==================== USER (opcional, apenas se precisar gerenciar usuários no admin) ====================
@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('email', 'nome', 'papel', 'is_active', 'last_login')
    search_fields = ('email', 'nome')
    list_filter = ('papel', 'is_active')
    ordering = ('email',)