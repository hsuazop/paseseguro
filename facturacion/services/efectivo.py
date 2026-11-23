import calendar
from datetime import date

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from accounts.permissions import colonias_permitidas
from colonias.models import Casa, Colonia
from core.models import registrar_auditoria
from facturacion.models import CuotaMensual, Pago

from .cuotas import obtener_monto_cuota
from .pagos import registrar_pago


@transaction.atomic
def registrar_efectivo(*, colonia, usuario, datos):
    if not colonias_permitidas(usuario).filter(pk=colonia.pk, activa=True).exists():
        raise PermissionDenied
    # Serializa altas y generación del mismo período dentro de esta residencial.
    Colonia.objects.select_for_update().get(pk=colonia.pk)
    casa = Casa.objects.select_for_update().get(
        pk=datos["casa"].pk, colonia=colonia, activa=True,
    )
    responsable = casa.responsable_actual
    if not responsable or not responsable.activo:
        raise ValidationError("La casa debe tener un vecino activo asignado.")
    anio, mes = datos["anio"], datos["mes"]
    cuota = CuotaMensual.objects.select_for_update().filter(
        responsable=responsable, colonia=colonia, anio=anio, mes=mes,
    ).first()
    if not cuota:
        monto = obtener_monto_cuota(casa, anio, mes)
        cuota = CuotaMensual.objects.create(
            casa=casa, responsable=responsable, colonia=colonia, anio=anio, mes=mes,
            monto_original=monto, saldo=monto,
            fecha_vencimiento=date(anio, mes, calendar.monthrange(anio, mes)[1]),
        )
        registrar_auditoria(usuario=usuario, accion="GENERACION_CUOTAS", objeto=cuota,
                            descripcion=f"Cuota de {cuota.periodo} generada al recibir efectivo.")
    if cuota.estado == CuotaMensual.Estado.PAGADA:
        raise ValidationError("El vecino ya pagó este mes y año.")
    return registrar_pago(
        casa=casa, responsable=responsable, usuario=usuario,
        fecha_pago=datos["fecha_pago"], monto_total=datos["monto_total"],
        metodo_pago=Pago.Metodo.EFECTIVO, observaciones=datos["observaciones"],
        aplicaciones=[{"cuota_id": cuota.pk, "monto": datos["monto_total"]}],
    )
