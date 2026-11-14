from django.utils import timezone

from accounts.permissions import colonias_permitidas
from .services.cuotas import generar_cuotas_mes


class CuotasAutomaticasMiddleware:
    """Ensure current charges even if the scheduled job was temporarily unavailable."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = request.user
        if (user.is_authenticated and not user.debe_cambiar_password
                and (user.es_superadmin or user.rol in {'RESIDENTE', 'ADMINISTRADOR', 'TESORERO'})
                and request.path.startswith(('/mi-cuenta/', '/dashboard/', '/tesoreria/', '/cuotas/', '/pagos/', '/reportes/'))):
            hoy = timezone.localdate()
            for colonia in colonias_permitidas(user).filter(activa=True):
                generar_cuotas_mes(colonia=colonia, anio=hoy.year, mes=hoy.month)
        return self.get_response(request)
