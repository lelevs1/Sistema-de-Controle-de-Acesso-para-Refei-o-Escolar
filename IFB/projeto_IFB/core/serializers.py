from rest_framework import serializers
from .models import User
from .models import Student

class StudentSerializer(serializers.ModelSerializer):
    foto_url = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Student
        fields = ['id', 'nome', 'matricula', 'data_nascimento', 'serie', 'foto', 'foto_url', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_foto_url(self, obj):
        if obj.foto:
            return obj.foto.url
        return None
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = '__all__'