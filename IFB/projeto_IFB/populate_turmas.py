import os
import django

# Configura o ambiente do Django para que o script possa acessar os modelos
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'setup.settings')
django.setup()

from core.models import Turma

TURMAS = [
    '2026.1.CSSB.INT.ELETRO.A', '2026.1.CSSB.INT.ELETRO.B', '2026.1.CSSB.INT.ELETRO.C', '2026.1.CSSB.INT.ELETRO.D',
    '2026.1.CSSB.SUB.ELETRO.A', '2026.1.CSSB.SUB.ELETRO.B', '2026.1.CSSB.SUB.ELETRO.C', '2026.1.CSSB.SUB.ELETRO.D',
    '2026.1.CSSB.SUB.MSI.A', '2026.1.CSSB.SUB.MSI.B', '2026.1.CSSB.SUB.MSI.C', '2026.1.CSSB.SUB.MSI.D',
    '2026.1.CSSB.SUB.MOD.A', '2026.1.CSSB.SUB.MOD.B', '2026.1.CSSB.SUB.MOD.C', '2026.1.CSSB.SUB.MOD.D',
    '2026.1.CSSB.PROEJA.MOD.A', '2026.1.CSSB.PROEJA.MOD.B', '2026.1.CSSB.PROEJA.MOD.C', '2026.1.CSSB.PROEJA.MOD.D',
    '2026.1.CSSB.BACH.CC.A', '2026.1.CSSB.BACH.CC.B', '2026.1.CSSB.BACH.CC.C', '2026.1.CSSB.BACH.CC.D',
    '2026.1.CSSB.LIC.COMP.A', '2026.1.CSSB.LIC.COMP.B', '2026.1.CSSB.LIC.COMP.C', '2026.1.CSSB.LIC.COMP.D',
    '2026.1.CSSB.LIC.FIS.A', '2026.1.CSSB.LIC.FIS.B', '2026.1.CSSB.LIC.FIS.C', '2026.1.CSSB.LIC.FIS.D',
    '2026.1.CSSB.TEC.AUTO.A', '2026.1.CSSB.TEC.AUTO.B', '2026.1.CSSB.TEC.AUTO.C', '2026.1.CSSB.TEC.AUTO.D',
    '2026.1.CSSB.TEC.MODA.A', '2026.1.CSSB.TEC.MODA.B', '2026.1.CSSB.TEC.MODA.C', '2026.1.CSSB.TEC.MODA.D',
    '2026.1.CSSB.FIC.LIBBAS.A', '2026.1.CSSB.FIC.LIBBAS.B', '2026.1.CSSB.FIC.LIBBAS.C', '2026.1.CSSB.FIC.LIBBAS.D',
    '2026.1.CSSB.FIC.LIBINT.A', '2026.1.CSSB.FIC.LIBINT.B', '2026.1.CSSB.FIC.LIBINT.C', '2026.1.CSSB.FIC.LIBINT.D',
    '2026.1.CSSB.FIC.REACT.A', '2026.1.CSSB.FIC.REACT.B', '2026.1.CSSB.FIC.REACT.C', '2026.1.CSSB.FIC.REACT.D',
    '2026.1.CSSB.QUAL.CUID.A', '2026.1.CSSB.QUAL.CUID.B', '2026.1.CSSB.QUAL.CUID.C', '2026.1.CSSB.QUAL.CUID.D',
    '2026.1.CSSB.QUAL.RECEP.A', '2026.1.CSSB.QUAL.RECEP.B', '2026.1.CSSB.QUAL.RECEP.C', '2026.1.CSSB.QUAL.RECEP.D'
]

def popular():
    print("Iniciando a inserção de turmas no banco de dados...")
    criadas = 0
    existentes = 0
    for nome_turma in TURMAS:
        turma, created = Turma.objects.get_or_create(nome=nome_turma)
        if created:
            criadas += 1
        else:
            existentes += 1
            
    print(f"Finalizado! {criadas} novas turmas criadas e {existentes} turmas já existiam.")

if __name__ == '__main__':
    popular()