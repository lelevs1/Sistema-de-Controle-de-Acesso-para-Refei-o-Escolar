import urllib.parse
import requests
import logging
from datetime import datetime, timedelta
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.shortcuts import redirect
from django.utils import timezone
from django.conf import settings
from django.http import JsonResponse
from django.db import models
from django.db.models import Count, Q
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import viewsets, status
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError

from .models import (
    User, Student, Digital, Almoco, LogLiberacao, Turma, Curso,
    Configuracao, PeriodoValidado, Ocorrencia
)
from .serializers import StudentSerializer, DigitalSerializer, ImportStudentSerializer
from .permissions import IsAdmin, IsAdminOrFiscal, IsAdminOrGestor, IsFiscal, IsAdminOrFiscalOrGestor
from .biometria import comparar_templates
from .utils import gerar_csv, gerar_pdf, registrar_log_configuracao

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
    email = request.data.get('email') or request.data.get('username')
    password = request.data.get('password')
    if email:
        email = User.objects.normalize_email(email.strip())
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
    email = User.objects.normalize_email(email.strip())

    allowed_domains = ["escola.gov.br", "educacao.gov.br"]
    domain = email.split("@")[-1].lower()
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
    email = User.objects.normalize_email(data['email'].strip())
    if User.objects.filter(email=email).exists():
        return Response({'error': 'Usuário já existe'}, status=400)
    user = User.objects.create_user(
        email=email,
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
    permission_classes = [IsAdminOrFiscalOrGestor]   # alterado para incluir gestor
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
            nome_curso = row.get('curso', '').strip()
            curso_obj = None
            if nome_curso:
                curso_obj, _ = Curso.objects.get_or_create(nome=nome_curso)

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

    # Verifica horário de funcionamento
    config = Configuracao.objects.first()
    if config:
        agora = timezone.now().time()
        if agora < config.horario_inicio or agora > config.horario_fim:
            return Response({'status': 'bloqueado', 'motivo': 'Fora do horário de funcionamento'}, status=403)

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

    # Verifica horário
    config = Configuracao.objects.first()
    if config:
        agora = timezone.now().time()
        if agora < config.horario_inicio or agora > config.horario_fim:
            return Response({'status': 'bloqueado', 'motivo': 'Fora do horário de funcionamento'}, status=403)

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

# ==================== ESTATÍSTICAS (básicas) ====================
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

# ==================== LOGS (COM OCULTAÇÃO PARA FISCAL) ====================
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
    data = []
    for log in logs:
        item = {
            'id': log.id,
            'tipo': log.tipo,
            'data_hora': log.data_hora,
            'observacao': log.observacao
        }
        if request.user.papel == 'admin':
            item['operador'] = log.operador.email if log.operador else None
        data.append(item)
    return Response(data)

# ==================== IDENTIFICAÇÃO (BUSCA EXATA) ====================
@api_view(['POST'])
def identificar_por_digital(request):
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

# ==================== DASHBOARD FISCAL ====================
@api_view(['GET'])
@permission_classes([IsFiscal])
def dashboard_fiscal(request):
    hoje = timezone.now().date()
    ultimos_30_dias = [hoje - timedelta(days=i) for i in range(30)]
    evolucao = []
    for dia in ultimos_30_dias:
        total = Almoco.objects.filter(data_hora__date=dia).count()
        biometria = Almoco.objects.filter(data_hora__date=dia, metodo='biometria').count()
        manual = total - biometria
        evolucao.append({
            'data': dia.isoformat(),
            'total': total,
            'biometria': biometria,
            'manual': manual
        })
    inicio_semana = hoje - timedelta(days=hoje.weekday())
    dias_semana = [inicio_semana + timedelta(days=i) for i in range(7)]
    semana = []
    for dia in dias_semana:
        total = Almoco.objects.filter(data_hora__date=dia).count()
        semana.append({'data': dia.isoformat(), 'total': total})

    mes_atual = hoje.replace(day=1)
    proximo_mes = (mes_atual + timedelta(days=32)).replace(day=1)
    almocos_mes = Almoco.objects.filter(data_hora__gte=mes_atual, data_hora__lt=proximo_mes)
    total_mes = almocos_mes.count()
    biometria_mes = almocos_mes.filter(metodo='biometria').count()
    manual_mes = total_mes - biometria_mes

    return Response({
        'evolucao_diaria': evolucao,
        'semana': semana,
        'mes': {
            'total': total_mes,
            'biometria': biometria_mes,
            'manual': manual_mes,
            'percentual_biometria': round(biometria_mes / total_mes * 100, 2) if total_mes else 0
        }
    })

# ==================== DASHBOARD GESTÃO ====================
@api_view(['GET'])
@permission_classes([IsAdminOrGestor])
def dashboard_gestao(request):
    hoje = timezone.now().date()
    mes_atual = hoje.replace(day=1)
    proximo_mes = (mes_atual + timedelta(days=32)).replace(day=1)
    almocos_periodo = Almoco.objects.filter(data_hora__gte=mes_atual, data_hora__lt=proximo_mes)

    turmas = Turma.objects.all()
    dados_turmas = []
    for turma in turmas:
        alunos_turma = Student.objects.filter(turma=turma, ativo=True).count()
        if alunos_turma == 0:
            continue
        total_almocos_turma = almocos_periodo.filter(estudante__turma=turma).count()
        media_por_aluno = round(total_almocos_turma / alunos_turma, 2) if alunos_turma else 0
        percentual = round((total_almocos_turma / (alunos_turma * 30)) * 100, 2) if alunos_turma else 0
        dados_turmas.append({
            'turma_id': turma.id,
            'turma_nome': turma.nome,
            'total_alunos': alunos_turma,
            'total_almocos': total_almocos_turma,
            'media_por_aluno': media_por_aluno,
            'percentual_comparecimento': percentual
        })

    cursos = Curso.objects.all()
    dados_cursos = []
    for curso in cursos:
        alunos_curso = Student.objects.filter(curso=curso, ativo=True).count()
        if alunos_curso == 0:
            continue
        total_almocos_curso = almocos_periodo.filter(estudante__curso=curso).count()
        media_por_aluno = round(total_almocos_curso / alunos_curso, 2) if alunos_curso else 0
        dados_cursos.append({
            'curso_id': curso.id,
            'curso_nome': curso.nome,
            'total_alunos': alunos_curso,
            'total_almocos': total_almocos_curso,
            'media_por_aluno': media_por_aluno
        })

    meses = []
    for i in range(12):
        data_inicio = hoje.replace(day=1) - timedelta(days=30 * i)
        data_inicio = data_inicio.replace(day=1)
        data_fim = (data_inicio + timedelta(days=32)).replace(day=1)
        total = Almoco.objects.filter(data_hora__gte=data_inicio, data_hora__lt=data_fim).count()
        meses.append({
            'mes': data_inicio.strftime('%Y-%m'),
            'total': total
        })
    meses.reverse()

    return Response({
        'por_turma': dados_turmas,
        'por_curso': dados_cursos,
        'evolucao_mensal': meses
    })

# ==================== RELATÓRIOS ====================
@api_view(['GET'])
@permission_classes([IsAdminOrGestor])
def relatorio_diario(request):
    data_str = request.query_params.get('data')
    if not data_str:
        return Response({'error': 'Parâmetro data obrigatório (YYYY-MM-DD)'}, status=400)
    try:
        data = datetime.strptime(data_str, '%Y-%m-%d').date()
    except ValueError:
        return Response({'error': 'Formato de data inválido. Use YYYY-MM-DD'}, status=400)

    almocos = Almoco.objects.filter(data_hora__date=data).select_related('estudante', 'operador')
    cabecalho = ['ID Almoço', 'Estudante', 'Matrícula', 'Método', 'Data/Hora', 'Operador', 'Observação']
    dados = [[
        a.id, a.estudante.nome, a.estudante.matricula,
        a.get_metodo_display(), a.data_hora.strftime('%d/%m/%Y %H:%M'),
        a.operador.email if a.operador else '---', a.observacao or ''
    ] for a in almocos]

    formato = request.query_params.get('formato', 'json').lower()
    if formato == 'csv':
        return gerar_csv(f'relatorio_diario_{data_str}', cabecalho, dados)
    elif formato == 'pdf':
        return gerar_pdf(f'relatorio_diario_{data_str}', f'Relatório Diário - {data_str}', cabecalho, dados)
    return Response({'dados': dados, 'total': len(dados)})

@api_view(['GET'])
@permission_classes([IsAdminOrGestor])
def relatorio_mensal(request):
    ano = request.query_params.get('ano')
    mes = request.query_params.get('mes')
    if not ano or not mes:
        return Response({'error': 'Parâmetros ano e mes obrigatórios'}, status=400)
    try:
        data_inicio = datetime(int(ano), int(mes), 1).date()
        if int(mes) == 12:
            data_fim = datetime(int(ano)+1, 1, 1).date()
        else:
            data_fim = datetime(int(ano), int(mes)+1, 1).date()
    except ValueError:
        return Response({'error': 'Ano/mês inválidos'}, status=400)

    almocos = Almoco.objects.filter(data_hora__gte=data_inicio, data_hora__lt=data_fim).select_related('estudante', 'operador')
    cabecalho = ['ID', 'Estudante', 'Matrícula', 'Data', 'Método', 'Operador']
    dados = [[
        a.id, a.estudante.nome, a.estudante.matricula,
        a.data_hora.strftime('%d/%m/%Y'), a.get_metodo_display(),
        a.operador.email if a.operador else '---'
    ] for a in almocos]

    formato = request.query_params.get('formato', 'json').lower()
    nome_arquivo = f'relatorio_mensal_{ano}_{mes}'
    if formato == 'csv':
        return gerar_csv(nome_arquivo, cabecalho, dados)
    elif formato == 'pdf':
        return gerar_pdf(nome_arquivo, f'Relatório Mensal - {data_inicio.strftime("%B %Y")}', cabecalho, dados)
    return Response({'dados': dados, 'total': len(dados)})

@api_view(['GET'])
@permission_classes([IsAdminOrFiscal])
def relatorio_estudante(request, estudante_id):
    try:
        estudante = Student.objects.get(id=estudante_id)
    except Student.DoesNotExist:
        return Response({'error': 'Estudante não encontrado'}, status=404)

    almocos = Almoco.objects.filter(estudante=estudante).order_by('-data_hora')
    cabecalho = ['ID', 'Data/Hora', 'Método', 'Operador', 'Observação']
    dados = [[
        a.id, a.data_hora.strftime('%d/%m/%Y %H:%M'),
        a.get_metodo_display(), a.operador.email if a.operador else '---',
        a.observacao or ''
    ] for a in almocos]

    formato = request.query_params.get('formato', 'json').lower()
    nome_arquivo = f'relatorio_estudante_{estudante.matricula}'
    if formato == 'csv':
        return gerar_csv(nome_arquivo, cabecalho, dados)
    elif formato == 'pdf':
        return gerar_pdf(nome_arquivo, f'Histórico de {estudante.nome} - {estudante.matricula}', cabecalho, dados)
    return Response({'estudante': {'id': estudante.id, 'nome': estudante.nome, 'matricula': estudante.matricula}, 'almocos': dados})

@api_view(['GET'])
@permission_classes([IsAdminOrGestor])
def relatorio_operador(request):
    inicio = request.query_params.get('inicio')
    fim = request.query_params.get('fim')
    if not inicio or not fim:
        return Response({'error': 'Parâmetros inicio e fim obrigatórios'}, status=400)
    try:
        data_ini = datetime.strptime(inicio, '%Y-%m-%d').date()
        data_fim = datetime.strptime(fim, '%Y-%m-%d').date()
    except ValueError:
        return Response({'error': 'Formato de data inválido. Use YYYY-MM-DD'}, status=400)

    operadores = User.objects.filter(papel__in=['operador', 'admin']).annotate(num_almocos=Count('almoco'))
    dados = []
    for op in operadores:
        almocos = Almoco.objects.filter(operador=op, data_hora__date__gte=data_ini, data_hora__date__lte=data_fim)
        total = almocos.count()
        biometria = almocos.filter(metodo='biometria').count()
        manual = total - biometria
        dados.append([op.email, total, biometria, manual])
    cabecalho = ['Operador', 'Total almoços', 'Biometria', 'Manual']
    formato = request.query_params.get('formato', 'json').lower()
    nome_arquivo = f'relatorio_operador_{inicio}_a_{fim}'
    if formato == 'csv':
        return gerar_csv(nome_arquivo, cabecalho, dados)
    elif formato == 'pdf':
        return gerar_pdf(nome_arquivo, f'Relatório por Operador ({inicio} a {fim})', cabecalho, dados)
    return Response({'dados': dados})

@api_view(['GET'])
@permission_classes([IsAdminOrGestor])
def relatorio_excecoes(request):
    inicio = request.query_params.get('inicio')
    fim = request.query_params.get('fim')
    if not inicio or not fim:
        return Response({'error': 'Parâmetros inicio e fim obrigatórios'}, status=400)
    try:
        data_ini = datetime.strptime(inicio, '%Y-%m-%d').date()
        data_fim = datetime.strptime(fim, '%Y-%m-%d').date()
    except ValueError:
        return Response({'error': 'Formato de data inválido. Use YYYY-MM-DD'}, status=400)

    excecoes = LogLiberacao.objects.filter(
        data_hora__date__gte=data_ini, data_hora__date__lte=data_fim,
        tipo='manual'
    ).select_related('estudante', 'operador')
    cabecalho = ['ID', 'Data', 'Estudante', 'Operador', 'Observação']
    dados = [[
        log.id, log.data_hora.strftime('%d/%m/%Y %H:%M'),
        log.estudante.nome, log.operador.email if log.operador else '---',
        log.observacao or ''
    ] for log in excecoes]

    formato = request.query_params.get('formato', 'json').lower()
    nome_arquivo = f'relatorio_excecoes_{inicio}_a_{fim}'
    if formato == 'csv':
        return gerar_csv(nome_arquivo, cabecalho, dados)
    elif formato == 'pdf':
        return gerar_pdf(nome_arquivo, f'Exceções de Liberação Manual', cabecalho, dados)
    return Response({'dados': dados, 'total': len(dados)})

@api_view(['GET'])
@permission_classes([IsAdminOrGestor])
def relatorio_pagamento(request):
    inicio = request.query_params.get('inicio')
    fim = request.query_params.get('fim')
    if not inicio or not fim:
        return Response({'error': 'Parâmetros inicio e fim obrigatórios'}, status=400)
    try:
        data_ini = datetime.strptime(inicio, '%Y-%m-%d').date()
        data_fim = datetime.strptime(fim, '%Y-%m-%d').date()
    except ValueError:
        return Response({'error': 'Formato de data inválido. Use YYYY-MM-DD'}, status=400)

    almocos = Almoco.objects.filter(data_hora__date__gte=data_ini, data_hora__date__lte=data_fim)
    dias = almocos.dates('data_hora', 'day').order_by('data_hora')
    dados = []
    for dia in dias:
        dia_almocos = almocos.filter(data_hora__date=dia)
        total = dia_almocos.count()
        biometria = dia_almocos.filter(metodo='biometria').count()
        manual = total - biometria
        dados.append([dia.strftime('%d/%m/%Y'), total, biometria, manual])
    cabecalho = ['Data', 'Total almoços', 'Biometria', 'Manual']
    formato = request.query_params.get('formato', 'json').lower()
    nome_arquivo = f'relatorio_pagamento_{inicio}_a_{fim}'
    if formato == 'csv':
        return gerar_csv(nome_arquivo, cabecalho, dados)
    elif formato == 'pdf':
        return gerar_pdf(nome_arquivo, f'Relatório de Pagamento (Diário)', cabecalho, dados)
    return Response({'dados': dados})

# ==================== VALIDAÇÃO FISCAL ====================
@api_view(['POST'])
@permission_classes([IsAdminOrFiscal])
def validar_periodo(request):
    data_inicio = request.data.get('data_inicio')
    data_fim = request.data.get('data_fim')
    if not data_inicio or not data_fim:
        return Response({'error': 'data_inicio e data_fim são obrigatórios'}, status=400)
    try:
        inicio = datetime.strptime(data_inicio, '%Y-%m-%d').date()
        fim = datetime.strptime(data_fim, '%Y-%m-%d').date()
    except ValueError:
        return Response({'error': 'Formato de data inválido. Use YYYY-MM-DD'}, status=400)
    if inicio > fim:
        return Response({'error': 'data_inicio deve ser menor ou igual a data_fim'}, status=400)

    if PeriodoValidado.objects.filter(data_inicio=inicio, data_fim=fim).exists():
        return Response({'error': 'Este período já foi validado e não pode ser alterado'}, status=400)

    almocos = Almoco.objects.filter(data_hora__date__gte=inicio, data_hora__date__lte=fim)
    total = almocos.count()
    if total == 0:
        return Response({'error': 'Não há refeições neste período'}, status=400)

    config = Configuracao.objects.first()
    if not config:
        return Response({'error': 'Valor por refeição não configurado. Solicite ao administrador.'}, status=400)
    valor_total = total * config.valor_refeicao

    periodo = PeriodoValidado.objects.create(
        data_inicio=inicio,
        data_fim=fim,
        total_refeicoes=total,
        valor_total=valor_total,
        fiscal=request.user,
        observacao=request.data.get('observacao', '')
    )
    return Response({
        'status': 'validado',
        'protocolo': periodo.protocolo,
        'total_refeicoes': total,
        'valor_total': float(valor_total),
        'data_validacao': periodo.data_validacao,
        'fiscal': request.user.email
    })

@api_view(['GET'])
@permission_classes([IsAdminOrFiscal])
def listar_periodos_validados(request):
    periodos = PeriodoValidado.objects.all().order_by('-data_validacao')
    data = [{
        'id': p.id,
        'data_inicio': p.data_inicio,
        'data_fim': p.data_fim,
        'total_refeicoes': p.total_refeicoes,
        'valor_total': float(p.valor_total),
        'protocolo': p.protocolo,
        'fiscal': p.fiscal.email if p.fiscal else None,
        'data_validacao': p.data_validacao,
        'observacao': p.observacao
    } for p in periodos]
    return Response(data)

# ==================== CONFIGURAÇÕES DO SISTEMA ====================
@api_view(['GET', 'PUT'])
@permission_classes([IsAdmin])
def configuracao_sistema(request):
    config, created = Configuracao.objects.get_or_create(pk=1)
    if request.method == 'GET':
        return Response({
            'id': config.id,
            'valor_refeicao': float(config.valor_refeicao),
            'horario_inicio': config.horario_inicio.strftime('%H:%M'),
            'horario_fim': config.horario_fim.strftime('%H:%M'),
            'updated_at': config.updated_at,
            'updated_by': config.updated_by.email if config.updated_by else None
        })
    elif request.method == 'PUT':
        old_valor = config.valor_refeicao
        old_inicio = config.horario_inicio
        old_fim = config.horario_fim

        if 'valor_refeicao' in request.data:
            config.valor_refeicao = request.data['valor_refeicao']
        if 'horario_inicio' in request.data:
            config.horario_inicio = request.data['horario_inicio']
        if 'horario_fim' in request.data:
            config.horario_fim = request.data['horario_fim']
        config.updated_by = request.user
        config.save()

        if str(old_valor) != str(config.valor_refeicao):
            registrar_log_configuracao(request.user, 'valor_refeicao', str(old_valor), str(config.valor_refeicao))
        if str(old_inicio) != str(config.horario_inicio):
            registrar_log_configuracao(request.user, 'horario_inicio', str(old_inicio), str(config.horario_inicio))
        if str(old_fim) != str(config.horario_fim):
            registrar_log_configuracao(request.user, 'horario_fim', str(old_fim), str(config.horario_fim))

        return Response({
            'message': 'Configuração atualizada com sucesso',
            'valor_refeicao': float(config.valor_refeicao),
            'horario_inicio': config.horario_inicio.strftime('%H:%M'),
            'horario_fim': config.horario_fim.strftime('%H:%M')
        })

# ==================== OCORRÊNCIAS ====================
@api_view(['POST'])
@permission_classes([IsAdminOrFiscal])
def registrar_ocorrencia(request):
    estudante_id = request.data.get('estudante_id')
    tipo = request.data.get('tipo')
    descricao = request.data.get('descricao')
    if not estudante_id or not tipo or not descricao:
        return Response({'error': 'estudante_id, tipo e descricao são obrigatórios'}, status=400)
    try:
        estudante = Student.objects.get(id=estudante_id)
    except Student.DoesNotExist:
        return Response({'error': 'Estudante não encontrado'}, status=404)
    ocorrencia = Ocorrencia.objects.create(
        estudante=estudante,
        operador=request.user if request.user.is_authenticated else None,
        tipo=tipo,
        descricao=descricao
    )
    return Response({
        'id': ocorrencia.id,
        'estudante': estudante.nome,
        'tipo': ocorrencia.tipo,
        'descricao': ocorrencia.descricao,
        'data_hora': ocorrencia.data_hora,
        'operador': request.user.email if request.user.is_authenticated else None
    }, status=201)

@api_view(['GET'])
@permission_classes([IsAdminOrGestor])
def listar_ocorrencias(request, estudante_id=None):
    if estudante_id:
        try:
            estudante = Student.objects.get(id=estudante_id)
        except Student.DoesNotExist:
            return Response({'error': 'Estudante não encontrado'}, status=404)
        ocorrencias = Ocorrencia.objects.filter(estudante=estudante).order_by('-data_hora')
    else:
        if request.user.papel != 'admin':
            return Response({'error': 'Permissão negada'}, status=403)
        ocorrencias = Ocorrencia.objects.all().order_by('-data_hora')
    data = [{
        'id': o.id,
        'estudante': o.estudante.nome,
        'tipo': o.tipo,
        'descricao': o.descricao,
        'data_hora': o.data_hora,
        'operador': o.operador.email if o.operador else None
    } for o in ocorrencias]
    return Response(data)
# ==================== ADMIN - ALTERAR PERÍODO VALIDADO ====================
@api_view(['PUT'])
@permission_classes([IsAdmin])
def alterar_periodo_validado(request, periodo_id):
    """
    PUT /api/admin/periodos/<id>/
    Permite ao administrador alterar um período já validado.
    Se total_refeicoes for alterado, o valor_total é recalculado automaticamente.
    """
    try:
        periodo = PeriodoValidado.objects.get(id=periodo_id)
    except PeriodoValidado.DoesNotExist:
        return Response({'error': 'Período não encontrado'}, status=404)

    old_total = periodo.total_refeicoes
    old_valor = periodo.valor_total
    old_obs = periodo.observacao

    # Atualiza total_refeicoes (e recalcula valor_total)
    if 'total_refeicoes' in request.data:
        periodo.total_refeicoes = request.data['total_refeicoes']
        config = Configuracao.objects.first()
        if config:
            periodo.valor_total = periodo.total_refeicoes * config.valor_refeicao
        else:
            periodo.valor_total = old_valor  # fallback

    if 'observacao' in request.data:
        periodo.observacao = request.data['observacao']

    periodo.save()

    # Logs
    if old_total != periodo.total_refeicoes:
        registrar_log_configuracao(request.user, f'periodo_{periodo.id}_total_refeicoes', str(old_total), str(periodo.total_refeicoes))
    if old_valor != periodo.valor_total:
        registrar_log_configuracao(request.user, f'periodo_{periodo.id}_valor_total', str(old_valor), str(periodo.valor_total))
    if old_obs != periodo.observacao:
        registrar_log_configuracao(request.user, f'periodo_{periodo.id}_observacao', old_obs or '', periodo.observacao or '')

    return Response({
        'id': periodo.id,
        'data_inicio': periodo.data_inicio,
        'data_fim': periodo.data_fim,
        'total_refeicoes': periodo.total_refeicoes,
        'valor_total': float(periodo.valor_total),
        'observacao': periodo.observacao,
        'protocolo': periodo.protocolo,
        'message': 'Período alterado com sucesso (log registrado)'
    })