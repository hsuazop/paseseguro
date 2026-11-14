from django.core.management.base import BaseCommand
from django.utils import timezone

from colonias.models import Colonia
from facturacion.services.cuotas import generar_cuotas_mes


class Command(BaseCommand):
    help = "Crea automáticamente las cuotas del mes actual usando la tarifa vigente; puede ejecutarse cada día."

    def handle(self, *args, **options):
        hoy = timezone.localdate()
        creadas = 0
        for colonia in Colonia.objects.filter(activa=True):
            resultado = generar_cuotas_mes(colonia=colonia, anio=hoy.year, mes=hoy.month)
            creadas += resultado['creadas']
            for error in set(resultado['errores']):
                self.stderr.write(f"Residencial {colonia.pk}: {error}")
        self.stdout.write(f"Cuotas automáticas {hoy:%m/%Y}: {creadas} creadas.")
