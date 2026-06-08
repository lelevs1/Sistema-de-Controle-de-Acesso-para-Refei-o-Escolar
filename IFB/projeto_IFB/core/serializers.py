from rest_framework import serializers
from .models import User, Student, Digital, Turma

class DigitalSerializer(serializers.ModelSerializer):
    class Meta:
        model = Digital
        fields = ['id', 'estudante', 'codigo_hex', 'dedo', 'created_at']
        read_only_fields = ['id', 'created_at']

class ImportStudentSerializer(serializers.Serializer):
    file = serializers.FileField()

    def validate_file(self, value):
        if not value.name.endswith(('.csv', '.xlsx')):
            raise serializers.ValidationError("Formato inválido. Envie CSV ou Excel.")
        return value

class StudentSerializer(serializers.ModelSerializer):
    foto_url = serializers.SerializerMethodField(read_only=True)
    turma_nome = serializers.SerializerMethodField(read_only=True)  # campo extra para exibir o nome da turma

    class Meta:
        model = Student
        fields = [
            'id', 'nome', 'matricula', 'data_nascimento',
            'curso', 'turma', 'turma_nome', 'foto', 'foto_url',
            'ativo', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_foto_url(self, obj):
        return obj.foto.url if obj.foto else None

    def get_turma_nome(self, obj):
        return obj.turma.nome if obj.turma else None

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = '__all__'
curso_nome = serializers.SerializerMethodField()

def get_curso_nome(self, obj):
    return obj.curso.nome if obj.curso else None