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


# ==================== CURSO ====================
class Curso(models.Model):
    nome = models.CharField('Nome do Curso', max_length=150, unique=True)

    class Meta:
        verbose_name = 'Curso'
        verbose_name_plural = 'Cursos'

    def __str__(self):
        return self.nome


# ==================== STUDENT ====================
class Student(models.Model):
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
        indexes = [
            models.Index(fields=['data_hora']),
            models.Index(fields=['estudante', 'data_hora']),
        ]

    def __str__(self):
        return f'{self.estudante.nome} - {self.data_hora.strftime("%d/%m/%Y %H:%M")}'


# ==================== CONFIGURAÇÃO DO SISTEMA ====================
class Configuracao(models.Model):
    valor_refeicao = models.DecimalField('Valor por refeição', max_digits=10, decimal_places=2, default=0.00)
    horario_inicio = models.TimeField('Horário de início da cantina', default='11:00')
    horario_fim = models.TimeField('Horário de fim da cantina', default='14:00')
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='configuracoes')

    class Meta:
        verbose_name = 'Configuração'
        verbose_name_plural = 'Configurações'

    def __str__(self):
        return f'Valor: R$ {self.valor_refeicao} - Horário: {self.horario_inicio} às {self.horario_fim}'


# ==================== LOG DE ALTERAÇÕES DE CONFIGURAÇÃO ====================
class LogConfiguracao(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    campo = models.CharField(max_length=100)
    valor_antigo = models.TextField(blank=True, null=True)
    valor_novo = models.TextField(blank=True, null=True)
    data_hora = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Log de Configuração'
        verbose_name_plural = 'Logs de Configuração'
        ordering = ['-data_hora']

    def __str__(self):
        return f'{self.usuario.email} alterou {self.campo} em {self.data_hora}'


# ==================== PERÍODO VALIDADO (FISCAL) ====================
class PeriodoValidado(models.Model):
    data_inicio = models.DateField()
    data_fim = models.DateField()
    total_refeicoes = models.IntegerField()
    valor_total = models.DecimalField(max_digits=12, decimal_places=2)
    protocolo = models.CharField(max_length=50, unique=True, editable=False)
    fiscal = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='validacoes')
    data_validacao = models.DateTimeField(auto_now_add=True)
    observacao = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = 'Período Validado'
        verbose_name_plural = 'Períodos Validados'
        unique_together = ['data_inicio', 'data_fim']

    def save(self, *args, **kwargs):
        if not self.protocolo:
            import hashlib, time
            raw = f"{self.data_inicio}{self.data_fim}{time.time()}{self.fiscal.id if self.fiscal else ''}"
            self.protocolo = hashlib.md5(raw.encode()).hexdigest()[:16].upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.data_inicio} a {self.data_fim} - Protocolo: {self.protocolo}'


# ==================== OCORRÊNCIA ====================
class Ocorrencia(models.Model):
    TIPO_CHOICES = [
        ('biometria', 'Problema na biometria'),
        ('comportamento', 'Comportamento do aluno'),
        ('outro', 'Outro'),
    ]
    estudante = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='ocorrencias')
    operador = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES)
    descricao = models.TextField()
    data_hora = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Ocorrência'
        verbose_name_plural = 'Ocorrências'
        ordering = ['-data_hora']

    def __str__(self):
        return f'{self.estudante.nome} - {self.tipo} - {self.data_hora}'