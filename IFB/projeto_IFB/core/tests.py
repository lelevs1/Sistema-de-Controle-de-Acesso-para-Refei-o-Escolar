from django.test import TestCase
from django.utils import timezone
from core.models import Student, Almoco, User

class VoucherTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email='test@test.com', nome='Teste', password='123', papel='admin')
        self.student = Student.objects.create(nome='Aluno', matricula='123', data_nascimento='2000-01-01')

    def test_nao_pode_almocar_duas_vezes_no_mesmo_dia(self):
        hoje = timezone.now().date()
        Almoco.objects.create(estudante=self.student, metodo='biometria')
        ja_almocou = Almoco.objects.filter(estudante=self.student, data_hora__date=hoje).exists()
        self.assertTrue(ja_almocou)