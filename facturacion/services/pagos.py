from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from core.models import registrar_auditoria
from facturacion.models import AplicacionPago, CuotaMensual, Pago, ReciboSecuencia

from .cuotas import recalcular_cuota


def _decimal(valor):
    try:
        return Decimal(str(valor)).quantize(Decimal("0.01"))
    except Exception as exc:
        raise ValidationError("Uno de los montos no es valido.") from exc


def _siguiente_recibo(anio):
    secuencia, _ = ReciboSecuencia.objects.select_for_update().get_or_create(anio=anio)
    secuencia.ultimo_numero += 1
    secuencia.save(update_fields=("ultimo_numero",))
    return f"REC-{anio}-{secuencia.ultimo_numero:06d}"


@transaction.atomic
def registrar_pago(
    *, casa, responsable, fecha_pago, monto_total, metodo_pago, aplicaciones,
    usuario, referencia="", observaciones="",
):
    monto_total = _decimal(monto_total)
    if monto_total <= 0:
        raise ValidationError("El monto recibido debe ser mayor que cero.")
    if not casa.activa:
        raise ValidationError("No se pueden registrar pagos para una casa inactiva.")
    if not responsable:
        raise ValidationError("La casa debe tener un responsable asignado.")
    if not aplicaciones:
        raise ValidationError("Seleccione al menos una cuota para aplicar el pago.")

    normalizadas = []
    total_aplicado = Decimal("0.00")
    ids = [int(item["cuota_id"]) for item in aplicaciones]
    if len(ids) != len(set(ids)):
        raise ValidationError("No puede seleccionar la misma cuota mas de una vez.")
    cuotas = {
        cuota.pk: cuota
        for cuota in CuotaMensual.objects.select_for_update().filter(pk__in=ids).select_related(
            "casa", "responsable", "colonia"
        )
    }
    if len(cuotas) != len(set(ids)):
        raise ValidationError("Una o mas cuotas seleccionadas no existen.")

    for item in aplicaciones:
        cuota = cuotas[int(item["cuota_id"])]
        monto = _decimal(item["monto"])
        if cuota.responsable_id != responsable.pk:
            raise ValidationError("Todas las cuotas deben pertenecer a la persona seleccionada.")
        if cuota.colonia_id != casa.colonia_id:
            raise ValidationError("Todas las cuotas deben pertenecer a la colonia seleccionada.")
        if cuota.estado == CuotaMensual.Estado.ANULADA:
            raise ValidationError(f"La cuota de {cuota.periodo} esta anulada.")
        if monto <= 0:
            raise ValidationError(f"El monto aplicado a {cuota.periodo} debe ser mayor que cero.")
        if monto > cuota.saldo:
            raise ValidationError(f"No puede aplicar mas de L {cuota.saldo:.2f} a {cuota.periodo}.")
        normalizadas.append((cuota, monto))
        total_aplicado += monto

    if total_aplicado != monto_total:
        raise ValidationError("El total aplicado debe ser igual al monto recibido.")

    pago = Pago.objects.create(
        numero_recibo=_siguiente_recibo(fecha_pago.year),
        casa=casa,
        colonia=casa.colonia,
        responsable=responsable,
        fecha_pago=fecha_pago,
        monto_total=monto_total,
        metodo_pago=metodo_pago,
        referencia=referencia.strip(),
        observaciones=observaciones.strip(),
        usuario_que_registra=usuario,
    )
    for cuota, monto in normalizadas:
        AplicacionPago.objects.create(pago=pago, cuota_mensual=cuota, monto_aplicado=monto)
        recalcular_cuota(cuota)

    registrar_auditoria(
        usuario=usuario,
        accion="CREACION_PAGO",
        objeto=pago,
        descripcion=f"Pago {pago.numero_recibo} registrado por L {pago.monto_total:.2f}.",
        nuevos={
            "responsable_id": responsable.pk,
            "residencia_id": casa.pk,
            "monto_total": str(monto_total),
            "aplicaciones": [{"cuota_id": c.pk, "monto": str(m)} for c, m in normalizadas],
        },
    )
    return pago


@transaction.atomic
def anular_pago(*, pago, motivo, usuario):
    pago = Pago.objects.select_for_update().get(pk=pago.pk)
    if pago.anulado:
        raise ValidationError("Este pago ya fue anulado.")
    if not motivo or len(motivo.strip()) < 5:
        raise ValidationError("Indique un motivo de anulacion de al menos 5 caracteres.")

    cuota_ids = pago.aplicaciones.values_list("cuota_mensual_id", flat=True)
    cuotas = list(
        CuotaMensual.objects.select_for_update().filter(pk__in=cuota_ids)
    )
    pago.anulado = True
    pago.motivo_anulacion = motivo.strip()
    pago.usuario_que_anula = usuario
    pago.fecha_anulacion = timezone.now()
    pago.save(update_fields=("anulado", "motivo_anulacion", "usuario_que_anula", "fecha_anulacion", "updated_at"))
    for cuota in cuotas:
        recalcular_cuota(cuota)

    registrar_auditoria(
        usuario=usuario,
        accion="ANULACION_PAGO",
        objeto=pago,
        descripcion=f"Pago {pago.numero_recibo} anulado: {pago.motivo_anulacion}",
        anteriores={"anulado": False},
        nuevos={"anulado": True, "motivo": pago.motivo_anulacion},
    )
    return pago
