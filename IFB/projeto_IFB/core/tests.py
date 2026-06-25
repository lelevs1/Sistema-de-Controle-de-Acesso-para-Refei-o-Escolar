from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
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

    def test_login_com_email_case_insensitive(self):
        client = APIClient()
        response = client.post('/api/login/', {'email': 'TEST@TEST.COM', 'password': '123'}, format='json')
        self.assertEqual(response.status_code, 200)

    def test_fiscal_deve_usar_google_login(self):
        User.objects.create_user(email='fiscal@test.com', nome='Fiscal', password='123', papel='fiscal')
        client = APIClient()
        response = client.post('/api/login/', {'email': 'fiscal@test.com', 'password': '123'}, format='json')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data.get('error'), 'Fiscais devem usar login com Google')