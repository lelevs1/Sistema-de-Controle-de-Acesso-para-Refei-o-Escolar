import os
import django

# Configura o ambiente do Django para que o script possa acessar os modelos
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'setup.settings')
django.setup()

from core.models import Curso

CURSOS = [
    'Técnico Integrado em Eletromecânica',
    'Técnico Subsequente em Eletromecânica',
    'Técnico Subsequente em Manutenção e Suporte em Informática',
    'Técnico Subsequente em Modelagem do Vestuário',
    'Técnico PROEJA em Modelagem e Vestuário',
    'Bacharelado em Ciência da Computação',
    'Licenciatura em Computação',
    'Licenciatura em Física',
    'Tecnológico em Automação Industrial',
    'Tecnológico em Design de Moda',
    'FIC Libras Básico',
    'FIC Libras Intermediário',
    'FIC Front-End com React',
    'Qualificação Cuidadora de Idosos',
    'Qualificação Recepcionista'
]

def popular():
    print("Iniciando a inserção de cursos no banco de dados...")
    criadas = 0
    existentes = 0
    for nome_curso in CURSOS:
        curso, created = Curso.objects.get_or_create(nome=nome_curso)
        if created:
            criadas += 1
        else:
            existentes += 1
            
    print(f"Finalizado! {criadas} novos cursos criados e {existentes} cursos já existiam.")

if __name__ == '__main__':
    popular()