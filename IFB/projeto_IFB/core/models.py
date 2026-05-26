from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.db import models

# ==================== TURMA ====================
class Turma(models.Model):
    nome = models.CharField('Nome da Turma', max_length=100, unique=True)
    turno = models.CharField('Turno', max_length=50, blank=True, null=True)

    class Meta:
        verbose_name = 'Turma'
        verbose_name_plural = 'Turmas'

    def __str__(self):
        return self.nome
#====================curso============
class Curso(models.Model):
    nome = models.CharField('Nome do Curso', max_length=150, unique=True)

    class Meta:
        verbose_name = 'Curso'
        verbose_name_plural = 'Cursos'

    def __str__(self):
        return self.nome
# ==================== STUDENT ====================
class Student(models.Model):
    CURSO_CHOICES = [
        ('Técnico Integrado em Eletromecânica', 'Técnico Integrado em Eletromecânica'),
        ('Técnico Subsequente em Eletromecânica', 'Técnico Subsequente en Eletromecânica'),
        ('Técnico Subsequente em Manutenção e Suporte em Informática', 'Técnico Subsequente em Manutenção e Suporte em Informática'),
        ('Técnico Subsequente em Modelagem do Vestuário', 'Técnico Subsequente em Modelagem do Vestuário'),
        ('Técnico PROEJA em Modelagem e Vestuário', 'Técnico PROEJA em Modelagem e Vestuário'),
        ('Bacharelado em Ciência da Computação', 'Bacharelado em Ciência da Computação'),
        ('Licenciatura em Computação', 'Licenciatura em Computação'),
        ('Licenciatura em Física', 'Licenciatura em Física'),
        ('Tecnológico em Automação Industrial', 'Tecnológico em Automação Industrial'),
        ('Tecnológico em Design de Moda', 'Tecnológico em Design de Moda'),
        ('FIC Libras Básico', 'FIC Libras Básico'),
        ('FIC Libras Intermediário', 'FIC Libras Intermediário'),
        ('FIC Front-End com React', 'FIC Front-End com React'),
        ('Qualificação Cuidadora de Idosos', 'Qualificação Cuidadora de Idosos'),
        ('Qualificação Recepcionista', 'Qualificação Recepcionista'),
    ]

    nome = models.CharField('Nome completo', max_length=200)
    matricula = models.CharField('Matrícula', max_length=20, unique=True)
    data_nascimento = models.DateField('Data de nascimento')
    curso = models.ForeignKey(Curso, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Curso', related_name='estudantes')
    turma = models.ForeignKey(Turma, on_delete=models.SET_NULL, null=True, blank=True, verbose_name='Turma', related_name='estudantes')
    foto = models.ImageField('Foto do estudante', upload_to='estudantes/fotos/', blank=True, null=True)
    ativo = models.BooleanField('Ativo', default=True)
    created_at = models.DateTimeField('Criado em', auto_now_add=True)
    updated_at = models.DateTimeField('Atualizado em', auto_now=True)

    class Meta:
        verbose_name = 'Estudante'
        verbose_name_plural = 'Estudantes'
        ordering = ['nome']

    def __str__(self):
        return f'{self.nome} - {self.matricula}'


# ==================== USER ====================
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


# ==================== DIGITAL ====================
class Digital(models.Model):
    DEDO_CHOICES = [
        ('polegar_d', 'Polegar Direito'),
        ('indicador_d', 'Indicador Direito'),
        ('medio_d', 'Médio Direito'),
        ('anelar_d', 'Anelar Direito'),
        ('minimo_d', 'Mínimo Direito'),
        ('polegar_e', 'Polegar Esquerdo'),
        ('indicador_e', 'Indicador Esquerdo'),
        ('medio_e', 'Médio Esquerdo'),
        ('anelar_e', 'Anelar Esquerdo'),
        ('minimo_e', 'Mínimo Esquerdo'),
    ]
    estudante = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='digitais')
    codigo_hex = models.CharField('Código hexadecimal', max_length=255, unique=True)
    dedo = models.CharField('Dedo', max_length=20, choices=DEDO_CHOICES, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Digital'
        verbose_name_plural = 'Digitais'
        unique_together = ['estudante', 'dedo']

    def __str__(self):
        return f'{self.estudante.nome} - {self.get_dedo_display() or "Dedo não especificado"}'


# ==================== LOG DE LIBERAÇÃO ====================
class LogLiberacao(models.Model):
    TIPO_CHOICES = [
        ('biometrica', 'Biométrica'),
        ('manual', 'Manual'),
    ]
    estudante = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='logs')
    operador = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    data_hora = models.DateTimeField(auto_now_add=True)
    observacao = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = 'Log de Liberação'
        verbose_name_plural = 'Logs de Liberação'
        ordering = ['-data_hora']

    def __str__(self):
        return f'{self.estudante.nome} - {self.tipo} - {self.data_hora.strftime("%d/%m/%Y %H:%M")}'


# ==================== ALMOÇO ====================
class Almoco(models.Model):
    METODO_CHOICES = [
        ('biometria', 'Biometria'),
        ('manual', 'Manual'),
    ]
    estudante = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='almocos')
    data_hora = models.DateTimeField(auto_now_add=True)
    metodo = models.CharField(max_length=20, choices=METODO_CHOICES)
    operador = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    observacao = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = 'Almoço'
        verbose_name_plural = 'Almoços'
        ordering = ['-data_hora']

    def __str__(self):
        return f'{self.estudante.nome} - {self.data_hora.strftime("%d/%m/%Y %H:%M")}'