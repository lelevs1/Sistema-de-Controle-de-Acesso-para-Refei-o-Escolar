# core/utils.py
import csv
from io import BytesIO, StringIO
from datetime import datetime
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from django.http import HttpResponse

def gerar_csv(nome_arquivo, cabecalho, dados):
    """Gera resposta HTTP com arquivo CSV."""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{nome_arquivo}.csv"'
    writer = csv.writer(response)
    writer.writerow(cabecalho)
    writer.writerows(dados)
    return response

def gerar_pdf(nome_arquivo, titulo, cabecalho, dados):
    """Gera resposta HTTP com arquivo PDF (tabela simples)."""
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{nome_arquivo}.pdf"'
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=landscape(A4), rightMargin=1*cm, leftMargin=1*cm, topMargin=1*cm, bottomMargin=1*cm)
    elementos = []

    # Estilos
    estilos = getSampleStyleSheet()
    estilo_titulo = ParagraphStyle('Titulo', parent=estilos['Title'], alignment=TA_CENTER, fontSize=14, spaceAfter=20)
    elementos.append(Paragraph(titulo, estilo_titulo))
    elementos.append(Spacer(1, 10))

    # Montar tabela
    tabela_dados = [cabecalho] + dados
    tabela = Table(tabela_dados, repeatRows=1)
    estilo_tabela = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
    ])
    tabela.setStyle(estilo_tabela)
    elementos.append(tabela)

    doc.build(elementos)
    pdf = buffer.getvalue()
    buffer.close()
    response.write(pdf)
    return response