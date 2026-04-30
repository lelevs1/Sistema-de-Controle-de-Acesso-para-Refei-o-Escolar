import urllib.parse
import requests
import logging
from django.shortcuts import redirect
from django.utils import timezone
from django.conf import settings
from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from .models import User
from .permissions import IsAdmin
from rest_framework import viewsets, status
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.response import Response
from .models import Student
from .serializers import StudentSerializer
from .permissions import IsAdminOrFiscal
import csv
import io
from rest_framework.parsers import MultiPartParser
from .serializers import ImportStudentSerializer
from .models import Digital
from .serializers import DigitalSerializer
from .models import User, Student, Digital
from .biometria import comparar_templates
#from .models import Almoco  # se for usar depois
@api_view(['POST'])
def identificar_por_digital(request):
    """
    Recebe o código hexadecimal da digital (template) e retorna os dados do aluno,
    desde que a digital esteja cadastrada e o aluno esteja ativo.
    """
    codigo_hex = request.data.get('codigo_hex')
    if not codigo_hex:
        return Response({'error': 'Código hexadecimal não informado'}, status=400)

    try:
        digital = Digital.objects.select_related('estudante').get(codigo_hex=codigo_hex)
    except Digital.DoesNotExist:
        return Response({'error': 'Digital não reconhecida'}, status=404)

    estudante = digital.estudante
    if not estudante.ativo:
        return Response({'error': 'Estudante inativo'}, status=403)

    # Opcional: registrar log de liberação (ver abaixo)
    # registrar_log_liberacao(estudante, tipo='biometrica', operador=None)

    return Response({
        'id': estudante.id,
        'nome': estudante.nome,
        'matricula': estudante.matricula,
        'serie': estudante.serie,
        'foto_url': estudante.foto.url if estudante.foto else None,
        'ativo': estudante.ativo
    })
@api_view(['POST'])
@permission_classes([IsAdminOrFiscal])
def cadastrar_digital(request, estudante_id):
    try:
        estudante = Student.objects.get(id=estudante_id)
    except Student.DoesNotExist:
        return Response({'error': 'Estudante não encontrado'}, status=404)

    codigo_hex = request.data.get('codigo_hex')
    dedo = request.data.get('dedo')
    if not codigo_hex:
        return Response({'error': 'código hexadecimal é obrigatório'}, status=400)

    # Verifica se o código já existe em algum aluno
    if Digital.objects.filter(codigo_hex=codigo_hex).exists():
        return Response({'error': 'Este código de digital já está cadastrado para outro aluno'}, status=400)

    digital = Digital.objects.create(estudante=estudante, codigo_hex=codigo_hex, dedo=dedo)
    serializer = DigitalSerializer(digital)
    return Response(serializer.data, status=201)


@api_view(['GET'])
@permission_classes([IsAdminOrFiscal])
def listar_digitais(request, estudante_id):
    try:
        estudante = Student.objects.get(id=estudante_id)
    except Student.DoesNotExist:
        return Response({'error': 'Estudante não encontrado'}, status=404)

    digitais = estudante.digitais.all()
    serializer = DigitalSerializer(digitais, many=True)
    return Response(serializer.data)


@api_view(['DELETE'])
@permission_classes([IsAdminOrFiscal])
def remover_digital(request, digital_id):
    try:
        digital = Digital.objects.get(id=digital_id)
    except Digital.DoesNotExist:
        return Response({'error': 'Digital não encontrada'}, status=404)
    digital.delete()
    return Response({'message': 'Digital removida com sucesso'})

@api_view(['POST'])
@permission_classes([IsAdminOrFiscal])
def importar_estudantes(request):
    serializer = ImportStudentSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=400)

    file = serializer.validated_data['file']
    data = file.read().decode('utf-8')
    csv_file = io.StringIO(data)
    reader = csv.DictReader(csv_file)

    expected_fields = ['nome', 'matricula', 'data_nascimento', 'serie']
    if not all(field in reader.fieldnames for field in expected_fields):
        return Response({'error': f'O CSV deve conter as colunas: {", ".join(expected_fields)}'}, status=400)

    criados = []
    erros = []
    for row_num, row in enumerate(reader, start=2):
        # Validação básica
        if Student.objects.filter(matricula=row['matricula']).exists():
            erros.append(f"Linha {row_num}: Matrícula {row['matricula']} já existe.")
            continue
        try:
            student = Student.objects.create(
                nome=row['nome'],
                matricula=row['matricula'],
                data_nascimento=row['data_nascimento'],
                serie=row['serie'],
                curso=row.get('curso', ''),
                turma=row.get('turma', ''),
                ativo=row.get('ativo', 'True').lower() in ['true', '1', 'sim']
            )
            criados.append(student.id)
        except Exception as e:
            erros.append(f"Linha {row_num}: {str(e)}")

    return Response({
        'importados': len(criados),
        'ids': criados,
        'erros': erros
    })
logger = logging.getLogger(__name__)

def test_api(request):
    return JsonResponse({"message": "API funcionando"})
def home(request):
    return JsonResponse({"message": "Bem-vindo à API do sistema"})

# Registro de usuário (apenas admin)
@api_view(['POST'])
@permission_classes([IsAdmin])
def register_user(request):
    data = request.data
    required = ['email', 'nome', 'papel']
    if not all(k in data for k in required):
        return Response({'error': 'Dados obrigatórios: email, nome, papel'}, status=400)
    if User.objects.filter(email=data['email']).exists():
        return Response({'error': 'Usuário já existe'}, status=400)
    user = User.objects.create_user(
        email=data['email'],
        nome=data['nome'],
        password=data.get('password'),  # opcional para OAuth
        papel=data['papel']
    )
    return Response({'message': 'Usuário criado com sucesso'})

# Login tradicional (apenas operador, empresa, gestor)
@api_view(['POST'])
def login(request):
    email = request.data.get('email')
    password = request.data.get('password')
    if not email or not password:
        return Response({'error': 'Email e senha obrigatórios'}, status=400)

    user = User.objects.filter(email=email).first()
    if not user or not user.check_password(password):
        return Response({'error': 'Credenciais inválidas'}, status=401)

    # Bloqueia login por senha para fiscais e admin
    if user.papel == 'fiscal':  # apenas fiscal deve usar Google (admin pode usar senha)
        return Response({'error': 'Fiscais devem usar login com Google'}, status=403)

    if not user.is_active:
        return Response({'error': 'Usuário desativado'}, status=403)

    user.ultimo_acesso = timezone.now()
    user.save()

    refresh = RefreshToken.for_user(user)
    return Response({
        'refresh': str(refresh),
        'access': str(refresh.access_token),
        'papel': user.papel,
        'email': user.email
    })

# Inicia fluxo OAuth Google
def google_login(request):
    base_url = "https://accounts.google.com/o/oauth2/v2/auth"
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "select_account",
    }
    url = f"{base_url}?{urllib.parse.urlencode(params)}"
    return redirect(url)

# Callback do Google
def google_callback(request):
    code = request.GET.get('code')
    if not code:
        return redirect("http://localhost:5173/login?error=missing_code")

    token_url = "https://oauth2.googleapis.com/token"
    data = {
        "code": code,
        "client_id": settings.GOOGLE_CLIENT_ID,
        "client_secret": settings.GOOGLE_CLIENT_SECRET,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "grant_type": "authorization_code",
    }
    try:
        token_response = requests.post(token_url, data=data, timeout=10)
        token_response.raise_for_status()
        token_data = token_response.json()
    except Exception as e:
        logger.error(f"Erro no token: {e}")
        return redirect("http://localhost:5173/login?error=token_failed")

    access_token = token_data.get("access_token")
    if not access_token:
        return redirect("http://localhost:5173/login?error=no_token")

    try:
        user_info = requests.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10
        ).json()
    except Exception as e:
        logger.error(f"Erro ao obter userinfo: {e}")
        return redirect("http://localhost:5173/login?error=userinfo_failed")

    email = user_info.get("email")
    if not email:
        return redirect("http://localhost:5173/login?error=no_email")

    # Restrição de domínio para fiscais e admin
    allowed_domains = ["escola.gov.br", "educacao.gov.br"]
    domain = email.split("@")[-1]
    if domain not in allowed_domains:
        return redirect("http://localhost:5173/login?error=domain_not_allowed")

    # Busca ou cria usuário
    user = User.objects.filter(email=email).first()
    if not user:
        # Cria como fiscal (padrão), admin pode ser promovido depois
        user = User.objects.create_user(
            email=email,
            nome=user_info.get('name', email.split('@')[0]),
            papel='fiscal',
            password=None
        )
        user.google_id = user_info.get('id')
        user.save()
    else:
        # Se já existe, mas papel não é fiscal/admin, bloqueia
        if user.papel not in ['fiscal', 'admin']:
            return redirect("http://localhost:5173/login?error=unauthorized")
        if not user.google_id:
            user.google_id = user_info.get('id')
            user.save()

    user.ultimo_acesso = timezone.now()
    user.save()

    refresh = RefreshToken.for_user(user)
    access_jwt = str(refresh.access_token)
    refresh_jwt = str(refresh)

    # Redireciona para o frontend com tokens
    frontend_url = f"http://localhost:5173/dashboard?access={access_jwt}&refresh={refresh_jwt}&papel={user.papel}"
    return redirect(frontend_url)

# Logout (invalida o refresh token - opcional)
@api_view(['POST'])
def logout(request):
    try:
        refresh_token = request.data.get('refresh')
        if refresh_token:
            token = RefreshToken(refresh_token)
            token.blacklist()  # requer 'rest_framework_simplejwt.token_blacklist' no INSTALLED_APPS
        return Response({'message': 'Logout realizado com sucesso'})
    except TokenError:
        return Response({'error': 'Token inválido'}, status=400)

# Perfil do usuário
@api_view(['GET'])
def perfil_usuario(request):
    if not request.user.is_authenticated:
        return Response({'error': 'Não autenticado'}, status=401)
    return Response({
        'email': request.user.email,
        'nome': request.user.nome,
        'papel': request.user.papel,
        'ultimo_acesso': request.user.ultimo_acesso,
    })

    # ========== VIEWSET ESTUDANTE (CRUD) ==========


class StudentViewSet(viewsets.ModelViewSet):
    """
    ViewSet completo para CRUD de estudantes.
    Suporta upload de foto via multipart/form-data.
    """
    queryset = Student.objects.all()
    serializer_class = StudentSerializer
    permission_classes = [IsAdminOrFiscal]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data)

    # ========== LOGS DE LIBERAÇÃO (RF04 e RF05) ==========


def registrar_log_liberacao(estudante, tipo, operador=None, observacao=''):
    LogLiberacao.objects.create(
        estudante=estudante,
        operador=operador,
        tipo=tipo,
        observacao=observacao
    )


@api_view(['GET'])
@permission_classes([IsAdminOrFiscal])
def logs_estudante(request, estudante_id):
    try:
        estudante = Student.objects.get(id=estudante_id)
    except Student.DoesNotExist:
        return Response({'error': 'Estudante não encontrado'}, status=404)
    logs = estudante.logs.all().order_by('-data_hora')
    data = [{
        'id': log.id,
        'tipo': log.tipo,
        'data_hora': log.data_hora,
        'operador': log.operador.email if log.operador else None,
        'observacao': log.observacao
    } for log in logs]
    return Response(data)


@api_view(['POST'])
def verificar_digital(request):
    """
    Recebe código hexadecimal da digital capturada, compara com todos os templates
    armazenados e retorna os dados do estudante se encontrar correspondência.
    """
    codigo_hex = request.data.get('codigo_hex')
    if not codigo_hex:
        return Response({'error': 'Código hexadecimal não informado'}, status=400)

    # Buscar todas as digitais cadastradas
    todas_digitais = Digital.objects.select_related('estudante').all()

    for digital in todas_digitais:
        try:
            # Compara o template recebido com o armazenado
            if comparar_templates(codigo_hex, digital.codigo_hex, security_level=4):
                estudante = digital.estudante
                if not estudante.ativo:
                    return Response({'status': 'aluno_inativo'}, status=403)

                # (Opcional) Aqui futuramente registraremos o almoço
                # Almoco.objects.create(estudante=estudante, metodo='biometria', operador=request.user if request.user.is_authenticated else None)

                return Response({
                    'status': 'encontrado',
                    'estudante': {
                        'id': estudante.id,
                        'nome': estudante.nome,
                        'matricula': estudante.matricula,
                        'serie': estudante.serie,
                        'foto_url': estudante.foto.url if estudante.foto else None,
                    }
                })
        except Exception as e:
            # Log do erro, mas continua tentando os próximos
            continue

    # Se nenhuma corresponder
    return Response({'status': 'nao_cadastrado'}, status=404)