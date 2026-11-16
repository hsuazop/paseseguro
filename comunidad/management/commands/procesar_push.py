import time
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.db import close_old_connections
from comunidad.push import procesar_lote


class Command(BaseCommand):
    help = 'Procesa la cola SOS. Usar --loop con supervisión para envío continuo.'
    def add_arguments(self, parser):
        parser.add_argument('--loop', action='store_true')
    def handle(self, *args, **options):
        if not all((settings.WEBPUSH_PRIVATE_KEY, settings.WEBPUSH_PUBLIC_KEY, settings.WEBPUSH_SUBJECT)):
            raise CommandError('Configura las tres variables WEBPUSH antes de iniciar.')
        while True:
            close_old_connections()
            count=procesar_lote()
            if not options['loop']:
                self.stdout.write(f'Entregas procesadas: {count}')
                return
            time.sleep(2)
