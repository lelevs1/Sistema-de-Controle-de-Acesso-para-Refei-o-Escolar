import urllib.parse
import requests
import logging
from datetime import datetime, timedelta
from django.shortcuts import redirect
from django.utils import timezone
from django.conf import settings
from django.http import JsonResponse
from django.db import models
from django.db.models import Count
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import viewsets, status
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError

from .models import User, Student, Digital, Almoco, LogLiberacao, Turma, Curso
from .serializers import StudentSerializer, DigitalSerializer, ImportStudentSerializer
from .permissions import IsAdmin, IsAdminOrFiscal
from .biometria import comparar_templates

import csv
import io

logger = logging.getLogger(__name__)

# ==================== UTILITÁRIOS ====================
def calcular_percentuais():
    hoje = timezone.now().date()
    almocos_hoje = Almoco.objects.filter(data_hora__date=hoje)
    total = almocos_hoje.count()
    biometria = almocos_hoje.filter(metodo='biometria').count()
    manual = total - biometria
    return {
        'total': total,
        'biometria': biometria,
        'manual': manual,
        'percentual_biometria': round(biometria / total * 100, 2) if total else 0
    }

def enviar_liberacao_websocket(estudante, almoco):
    """Envia evento de liberação via WebSocket (se channels estiver configurado)"""
    try:
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        channel_layer = get_channel_layer()
        if channel_layer:
            async_to_sync(channel_layer.group_send)(
                'liberacoes',
                {
                    'type': 'nova_liberacao',
                    'data': {
                        'estudante_id': estudante.id,
                        'nome': estudante.nome,
                        'matricula': estudante.matricula,
                        'metodo': almoco.metodo,
                        'data_hora': almoco.data_hora.isoformat(),
                        'observacao': almoco.observacao,
                        'percentuais': calcular_percentuais()
                    }
                }
            )
    except Exception as e:
        print(f"WebSocket não enviado: {e}")

# ==================== VIEWS PÚBLICAS ====================
def test_api(request):
    return JsonResponse({"message": "API funcionando"})

def home(request):
    return JsonResponse({"message": "Bem-vindo à API do sistema"})

@api_view(['POST'])
def login(request):
    email = request.data.get('email')
    password = request.data.get('password')
    if not email or not password:
        return Response({'error': 'Email e senha obrigatórios'}, status=400)

    user = User.objects.filter(email=email).first()
    if not user or not user.check_password(password):
        return Response({'error': 'Credenciais inválidas'}, status=401)

    if user.papel == 'fiscal':
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

# ==================== GOOGLE OAUTH ====================
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

    allowed_domains = ["escola.gov.br", "educacao.gov.br"]
    domain = email.split("@")[-1]
    if domain not in allowed_domains:
        return redirect("http://localhost:5173/login?error=domain_not_allowed")

    user = User.objects.filter(email=email).first()
    if not user:
        user = User.objects.create_user(
            email=email,
            nome=user_info.get('name', email.split('@')[0]),
            papel='fiscal',
            password=None
        )
        user.google_id = user_info.get('id')
        user.save()
    else:
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

    frontend_url = f"http://localhost:5173/dashboard?access={access_jwt}&refresh={refresh_jwt}&papel={user.papel}"
    return redirect(frontend_url)

# ==================== USUÁRIOS E PERFIL ====================
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
        password=data.get('password'),
        papel=data['papel']
    )
    return Response({'message': 'Usuário criado com sucesso'})

@api_view(['POST'])
def logout(request):
    try:
        refresh_token = request.data.get('refresh')
        if refresh_token:
            token = RefreshToken(refresh_token)
            token.blacklist()
        return Response({'message': 'Logout realizado com sucesso'})
    except TokenError:
        return Response({'error': 'Token inválido'}, status=400)

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

# ==================== CRUD ESTUDANTES (VIEWSET) ====================
class StudentViewSet(viewsets.ModelViewSet):
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

# ==================== IMPORTAR ESTUDANTES (CSV) ====================
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

    expected_fields = ['nome', 'matricula', 'data_nascimento']
    if not all(field in reader.fieldnames for field in expected_fields):
        return Response({'error': f'O CSV deve conter as colunas: {", ".join(expected_fields)} (curso, turma e ativo são opcionais)'}, status=400)

    criados = []
    erros = []
    for row_num, row in enumerate(reader, start=2):
        if Student.objects.filter(matricula=row['matricula']).exists():
            erros.append(f"Linha {row_num}: Matrícula {row['matricula']} já existe.")
            continue

        try:
            # Tratamento do curso (ForeignKey)
            nome_curso = row.get('curso', '').strip()
            curso_obj = None
            if nome_curso:
                curso_obj, _ = Curso.objects.get_or_create(nome=nome_curso)

            # Tratamento da turma (ForeignKey)
            nome_turma = row.get('turma', '').strip()
            turma_obj = None
            if nome_turma:
                turma_obj, _ = Turma.objects.get_or_create(nome=nome_turma)

            student = Student.objects.create(
                nome=row['nome'],
                matricula=row['matricula'],
                data_nascimento=row['data_nascimento'],
                curso=curso_obj,
                turma=turma_obj,
                ativo=row.get('ativo', 'True').lower() in ['true', '1', 'sim']
            )
            criados.append(student.id)
        except Exception as e:
            erros.append(f"Linha {row_num}: {str(e)}")

    return Response({'importados': len(criados), 'ids': criados, 'erros': erros})

# ==================== DIGITAIS ====================
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

# ==================== VERIFICAÇÃO BIOMÉTRICA (com almoço) ====================
@api_view(['POST'])
def verificar_digital(request):
    codigo_hex = request.data.get('codigo_hex')
    if not codigo_hex:
        return Response({'error': 'Código hexadecimal não informado'}, status=400)

    todas_digitais = Digital.objects.select_related('estudante__turma', 'estudante__curso').all()
    for digital in todas_digitais:
        if comparar_templates(codigo_hex, digital.codigo_hex, security_level=4):
            estudante = digital.estudante
            if not estudante.ativo:
                return Response({'status': 'bloqueado', 'motivo': 'Aluno inativo'}, status=403)

            hoje = timezone.now().date()
            if Almoco.objects.filter(estudante=estudante, data_hora__date=hoje).exists():
                return Response({'status': 'bloqueado', 'motivo': 'Já almoçou hoje'}, status=403)

            almoco = Almoco.objects.create(
                estudante=estudante,
                metodo='biometria',
                operador=request.user if request.user.is_authenticated else None,
                observacao='Liberação via biometria'
            )
            enviar_liberacao_websocket(estudante, almoco)
            return Response({
                'status': 'liberado',
                'estudante': {
                    'id': estudante.id,
                    'nome': estudante.nome,
                    'matricula': estudante.matricula,
                    'curso': estudante.curso.nome if estudante.curso else None,
                    'turma': estudante.turma.nome if estudante.turma else None,
                    'foto_url': estudante.foto.url if estudante.foto else None,
                },
                'mensagem': f'Almoço liberado para {estudante.nome}'
            })
    return Response({'status': 'nao_cadastrado', 'motivo': 'Digital não reconhecida'}, status=404)

# ==================== LIBERAÇÃO MANUAL ====================
@api_view(['POST'])
@permission_classes([IsAdminOrFiscal])
def liberar_manual(request):
    estudante_id = request.data.get('estudante_id')
    observacao = request.data.get('observacao', '').strip()
    if not estudante_id:
        return Response({'error': 'estudante_id é obrigatório'}, status=400)
    if not observacao:
        return Response({'error': 'Observação (motivo) é obrigatória'}, status=400)

    try:
        estudante = Student.objects.get(id=estudante_id)
    except Student.DoesNotExist:
        return Response({'error': 'Estudante não encontrado'}, status=404)

    if not estudante.ativo:
        return Response({'status': 'bloqueado', 'motivo': 'Aluno inativo'}, status=403)

    hoje = timezone.now().date()
    if Almoco.objects.filter(estudante=estudante, data_hora__date=hoje).exists():
        return Response({'status': 'bloqueado', 'motivo': 'Já almoçou hoje'}, status=400)

    almoco = Almoco.objects.create(
        estudante=estudante,
        metodo='manual',
        operador=request.user,
        observacao=observacao
    )
    enviar_liberacao_websocket(estudante, almoco)
    return Response({
        'status': 'liberado',
        'almoco_id': almoco.id,
        'mensagem': f'Almoço manual registrado para {estudante.nome}'
    })

# (opcional, compatibilidade com versão antiga – pode ser removida)
@api_view(['POST'])
@permission_classes([IsAdminOrFiscal])
def registrar_almoco_manual(request, estudante_id):
    return liberar_manual(request)

# ==================== BUSCA DE ESTUDANTES ====================
@api_view(['GET'])
@permission_classes([IsAdminOrFiscal])
def buscar_estudantes(request):
    query = request.query_params.get('q', '').strip()
    if not query:
        return Response({'error': 'Parâmetro de busca "q" é obrigatório'}, status=400)

    estudantes = Student.objects.filter(
        models.Q(nome__icontains=query) | models.Q(matricula__icontains=query)
    ).select_related('turma', 'curso')

    resultados = []
    for est in estudantes:
        resultados.append({
            'id': est.id,
            'nome': est.nome,
            'matricula': est.matricula,
            'turma': est.turma.nome if est.turma else None,
            'curso': est.curso.nome if est.curso else None,
            'foto_url': est.foto.url if est.foto else None,
        })
    return Response(resultados)

# ==================== ESTATÍSTICAS ====================
@api_view(['GET'])
@permission_classes([IsAdminOrFiscal])
def estatisticas_hoje(request):
    hoje = timezone.now().date()
    almocos_hoje = Almoco.objects.filter(data_hora__date=hoje)
    total = almocos_hoje.count()
    por_hora = almocos_hoje.extra({'hora': "strftime('%H', data_hora)"}).values('hora').annotate(total=Count('id'))
    ontem = hoje - timedelta(days=1)
    total_ontem = Almoco.objects.filter(data_hora__date=ontem).count()
    variacao = ((total - total_ontem) / total_ontem * 100) if total_ontem else 0
    return Response({
        'total_hoje': total,
        'por_hora': list(por_hora),
        'total_ontem': total_ontem,
        'variacao_percentual': round(variacao, 2)
    })

@api_view(['GET'])
@permission_classes([IsAdminOrFiscal])
def estatisticas_semana(request):
    hoje = timezone.now().date()
    inicio_semana = hoje - timedelta(days=hoje.weekday())
    dias = [inicio_semana + timedelta(days=i) for i in range(7)]
    dados = []
    for dia in dias:
        total = Almoco.objects.filter(data_hora__date=dia).count()
        dados.append({
            'data': dia.strftime('%Y-%m-%d'),
            'dia_semana': dia.strftime('%A'),
            'total': total
        })
    return Response(dados)

@api_view(['GET'])
@permission_classes([IsAdminOrFiscal])
def estatisticas_mensal(request):
    hoje = timezone.now().date()
    mes_atual = hoje.replace(day=1)
    proximo_mes = (mes_atual + timedelta(days=32)).replace(day=1)
    almocos = Almoco.objects.filter(data_hora__gte=mes_atual, data_hora__lt=proximo_mes)
    total = almocos.count()
    por_metodo = almocos.values('metodo').annotate(total=Count('id'))
    biometria = next((item['total'] for item in por_metodo if item['metodo'] == 'biometria'), 0)
    manual = next((item['total'] for item in por_metodo if item['metodo'] == 'manual'), 0)
    perc_biometria = (biometria / total * 100) if total else 0
    perc_manual = (manual / total * 100) if total else 0
    detalhes_por_dia = list(almocos.extra({'dia': "strftime('%d', data_hora)"}).values('dia').annotate(total=Count('id')))
    return Response({
        'mes': mes_atual.strftime('%B %Y'),
        'total': total,
        'biometria': biometria,
        'manual': manual,
        'percentual_biometria': round(perc_biometria, 2),
        'percentual_manual': round(perc_manual, 2),
        'detalhes_por_dia': detalhes_por_dia
    })

# ==================== LOGS (OPCIONAL) ====================
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

# ==================== IDENTIFICAÇÃO (BUSCA EXATA) ====================
@api_view(['POST'])
def identificar_por_digital(request):
    """
    Versão simples: busca exata do código hex (sem registro de almoço).
    """
    codigo_hex = request.data.get('codigo_hex')
    if not codigo_hex:
        return Response({'error': 'Código hexadecimal não informado'}, status=400)
    try:
        digital = Digital.objects.select_related('estudante__turma', 'estudante__curso').get(codigo_hex=codigo_hex)
    except Digital.DoesNotExist:
        return Response({'error': 'Digital não reconhecida'}, status=404)
    estudante = digital.estudante
    if not estudante.ativo:
        return Response({'error': 'Estudante inativo'}, status=403)
    return Response({
        'id': estudante.id,
        'nome': estudante.nome,
        'matricula': estudante.matricula,
        'curso': estudante.curso.nome if estudante.curso else None,
        'turma': estudante.turma.nome if estudante.turma else None,
        'foto_url': estudante.foto.url if estudante.foto else None,
        'ativo': estudante.ativo
    })