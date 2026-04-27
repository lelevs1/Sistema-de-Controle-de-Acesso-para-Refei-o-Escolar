from django.contrib import admin
from django.contrib import admin
from .models import Student

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('nome', 'matricula', 'serie', 'data_nascimento')
    search_fields = ('nome', 'matricula')
    list_filter = ('serie',)
# Register your models here.
