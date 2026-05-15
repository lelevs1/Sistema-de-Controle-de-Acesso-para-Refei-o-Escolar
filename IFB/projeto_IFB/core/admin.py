from django.contrib import admin
from .models import Student, Turma

@admin.register(Turma)
class TurmaAdmin(admin.ModelAdmin):
    list_display = ('nome', 'turno')
    search_fields = ('nome',)

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('nome', 'matricula', 'curso', 'turma', 'data_nascimento')
    search_fields = ('nome', 'matricula')
    list_filter = ('curso', 'turma')
# Register your models here.
