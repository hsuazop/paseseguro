import json
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from colonias.models import Colonia
from accesos.models import VehiculoColonia
from accesos.importar_padron import leer_padron


class Command(BaseCommand):
    help = 'Importa el padrón Excel, conservando filas originales. Repetir el mismo archivo no duplica ni sobrescribe registros.'

    def add_arguments(self, parser):
        parser.add_argument('archivo')
        parser.add_argument('--colonia-id', type=int, required=True)
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **options):
        try:
            colonia = Colonia.objects.get(pk=options['colonia_id'], activa=True)
            rows, report = leer_padron(options['archivo'])
        except (Colonia.DoesNotExist, ValueError, OSError) as exc:
            raise CommandError(str(exc)) from exc
        report.update(colonia_id=colonia.pk, colonia=colonia.nombre, creados=0, existentes=0, simulacion=options['dry_run'])
        with transaction.atomic():
            for row in rows:
                if VehiculoColonia.objects.filter(colonia=colonia, clave_importacion=row['clave_importacion']).exists():
                    report['existentes'] += 1
                    continue
                obj = VehiculoColonia(colonia=colonia, **row)
                obj.full_clean()
                if not options['dry_run']: obj.save()
                report['creados'] += 1
        self.stdout.write(json.dumps(report, ensure_ascii=False))
