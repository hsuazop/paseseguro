import calendar
from datetime import date

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from accounts.permissions import colonias_permitidas
from django.core.validators import validate_email
from colonias.models import Casa, Colonia
from core.models import registrar_auditoria
from facturacion.models import CuotaMensual, Pago
from residentes.models import Responsable
from residentes.services import asignar_responsable, crear_usuario_residente

from .cuotas import obtener_monto_cuota
from .pagos import registrar_pago


@transaction.atomic
def registrar_efectivo(*, colonia, usuario, datos):
    if not colonias_permitidas(usuario).filter(pk=colonia.pk, activa=True).exists():
        raise PermissionDenied
    # Serializa altas y generación del mismo período dentro de esta residencial.
    Colonia.objects.select_for_update().get(pk=colonia.pk)
    temporal = None
    if datos["tipo"] == "nuevo":
        correo = (datos.get("correo") or "").strip()
        validate_email(correo)
        casa, _ = Casa.objects.get_or_create(
            colonia=colonia, codigo=datos["codigo_casa"],
            defaults={"numero": datos["codigo_casa"]},
        )
        casa = Casa.objects.select_for_update().get(pk=casa.pk)
        if not casa.activa or casa.responsable_actual_id:
            raise ValidationError("La casa ya tiene responsable o está inactiva.")
        responsable = Responsable(
            nombre_completo=datos["nombre_completo"], identidad=datos["identidad"],
            telefono=datos["telefono"], correo=correo, creado_por=usuario,
        )
        responsable.full_clean()
        responsable.save()
        _, temporal = crear_usuario_residente(responsable)
        asignar_responsable(casa=casa, responsable=responsable, usuario=usuario)
        registrar_auditoria(usuario=usuario, accion="CREACION_RESPONSABLE", objeto=responsable,
                            descripcion="Vecino registrado al recibir pago en efectivo.")
    else:
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
    pago = registrar_pago(
        casa=casa, responsable=responsable, usuario=usuario,
        fecha_pago=datos["fecha_pago"], monto_total=datos["monto_total"],
        metodo_pago=Pago.Metodo.EFECTIVO, observaciones=datos["observaciones"],
        aplicaciones=[{"cuota_id": cuota.pk, "monto": datos["monto_total"]}],
    )
    return pago, temporal
