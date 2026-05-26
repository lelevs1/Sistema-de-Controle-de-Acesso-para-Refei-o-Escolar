from django.core.management.base import BaseCommand
from django.utils import timezone

class Command(BaseCommand):
    help = 'Renova os vouchers diários (lógica já é automática baseada em data)'

    def handle(self, *args, **kwargs):
        self.stdout.write(f'[{timezone.now()}] Job de renovação executado com sucesso.')