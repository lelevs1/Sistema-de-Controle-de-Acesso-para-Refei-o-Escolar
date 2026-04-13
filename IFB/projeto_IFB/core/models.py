from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.db import models

class Student(models.Model):
    SERIE_CHOICES = [
        ('6EF', '6º Ano EF'),
        ('7EF', '7º Ano EF'),
        ('8EF', '8º Ano EF'),
        ('9EF', '9º Ano EF'),
        ('1EM', '1º Ano EM'),
        ('2EM', '2º Ano EM'),
        ('3EM', '3º Ano EM'),
    ]

    nome = models.CharField('Nome completo', max_length=200)
    matricula = models.CharField('Matrícula', max_length=20, unique=True)
    data_nascimento = models.DateField('Data de nascimento')
    serie = models.CharField('Série/Ano', max_length=3, choices=SERIE_CHOICES)
    foto = models.ImageField('Foto do estudante', upload_to='estudantes/fotos/', blank=True, null=True)
    created_at = models.DateTimeField('Criado em', auto_now_add=True)
    updated_at = models.DateTimeField('Atualizado em', auto_now=True)

    class Meta:
        verbose_name = 'Estudante'
        verbose_name_plural = 'Estudantes'
        ordering = ['nome']

    def __str__(self):
        return f'{self.nome} - {self.matricula}'
class UserManager(BaseUserManager):
    def create_user(self, email, nome, password=None, papel='operador'):
        if not email:
            raise ValueError('Email é obrigatório')
        email = self.normalize_email(email)
        user = self.model(email=email, nome=nome, papel=papel)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, nome, password=None):
        user = self.create_user(email, nome, password, papel='admin')
        user.is_superuser = True
        user.is_staff = True
        user.save(using=self._db)
        return user

class User(AbstractBaseUser, PermissionsMixin):
    PAPEL_CHOICES = [
        ('operador', 'Operador'),
        ('empresa', 'Empresa'),
        ('gestor', 'Gestor'),
        ('fiscal', 'Fiscal'),
        ('admin', 'Administrador'),
    ]
    email = models.EmailField(unique=True)
    nome = models.CharField(max_length=255)
    papel = models.CharField(max_length=20, choices=PAPEL_CHOICES, default='operador')
    google_id = models.CharField(max_length=100, blank=True, null=True)
    ultimo_acesso = models.DateTimeField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['nome']

    objects = UserManager()

    def __str__(self):
        return self.email
