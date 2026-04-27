from rest_framework import serializers
from .models import User
from .models import Student
from .models import Digital

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

    class Meta:
        model = Student
        fields = ['id', 'nome', 'matricula', 'data_nascimento', 'serie', 'foto', 'foto_url',
                  'ativo', 'curso', 'turma', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_foto_url(self, obj):
        if obj.foto:
            return obj.foto.url
        return None
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = '__all__'