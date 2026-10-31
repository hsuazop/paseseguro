import calendar
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q, Sum

from colonias.models import Casa
from core.models import registrar_auditoria
from facturacion.models import AplicacionPago, CuotaMensual, TarifaColonia, TarifaEspecialCasa


CENTAVOS = Decimal("0.01")


def _vigente(queryset, fecha):
    return queryset.filter(activa=True, fecha_inicio__lte=fecha).filter(
        Q(fecha_fin__isnull=True) | Q(fecha_fin__gte=fecha)
    )


def obtener_monto_cuota(casa, anio, mes):
    fecha = date(anio, mes, 1)
    tarifa_base = _vigente(TarifaColonia.objects.filter(colonia=casa.colonia), fecha).order_by("-fecha_inicio").first()
    if not tarifa_base:
        raise ValidationError(f"{casa.colonia} no tiene una tarifa base vigente para {mes:02d}/{anio}.")

    especial = _vigente(TarifaEspecialCasa.objects.filter(casa=casa), fecha).order_by("-fecha_inicio").first()
    if not especial:
        return tarifa_base.monto.quantize(CENTAVOS)
    if especial.tipo == TarifaEspecialCasa.Tipo.MONTO_FIJO:
        return especial.monto.quantize(CENTAVOS)
    return (tarifa_base.monto * especial.porcentaje / Decimal("100")).quantize(CENTAVOS, rounding=ROUND_HALF_UP)


@transaction.atomic
def generar_cuotas_mes(*, colonia, anio, mes, usuario=None):
    if mes not in range(1, 13):
        raise ValidationError("El mes debe estar entre 1 y 12.")
    creadas = 0
    existentes = 0
    errores = []
    ultimo_dia = calendar.monthrange(anio, mes)[1]

    vistos = set()
    casas = Casa.objects.select_related("colonia", "responsable_actual").filter(
        colonia=colonia,
        activa=True,
        responsable_actual__isnull=False,
        responsable_actual__activo=True,
    ).order_by("pk")
    for casa in casas:
        responsable = casa.responsable_actual
        if responsable.pk in vistos:
            continue
        vistos.add(responsable.pk)
        if CuotaMensual.objects.filter(
            responsable=responsable,
            colonia=colonia,
            anio=anio,
            mes=mes,
        ).exists():
            existentes += 1
            continue
        try:
            monto = obtener_monto_cuota(casa, anio, mes)
        except ValidationError as exc:
            errores.extend(exc.messages)
            continue
        CuotaMensual.objects.create(
            casa=casa,
            responsable=responsable,
            colonia=colonia,
            anio=anio,
            mes=mes,
            monto_original=monto,
            monto_pagado=Decimal("0.00"),
            saldo=monto,
            estado=CuotaMensual.Estado.PENDIENTE,
            fecha_vencimiento=date(anio, mes, ultimo_dia),
        )
        creadas += 1

    if creadas:
        registrar_auditoria(
            usuario=usuario,
            accion="GENERACION_CUOTAS",
            objeto=colonia,
            descripcion=f"Se generaron {creadas} cuotas para {mes:02d}/{anio}.",
            nuevos={"anio": anio, "mes": mes, "creadas": creadas, "existentes": existentes},
        )
    return {"creadas": creadas, "existentes": existentes, "errores": errores}


def recalcular_cuota(cuota):
    if cuota.estado == CuotaMensual.Estado.ANULADA:
        return cuota
    pagado = cuota.aplicaciones.filter(pago__anulado=False).aggregate(total=Sum("monto_aplicado"))["total"] or Decimal("0.00")
    pagado = pagado.quantize(CENTAVOS)
    saldo = max(cuota.monto_original - pagado, Decimal("0.00")).quantize(CENTAVOS)
    if pagado <= 0:
        estado = CuotaMensual.Estado.PENDIENTE
    elif pagado < cuota.monto_original:
        estado = CuotaMensual.Estado.PARCIAL
    else:
        estado = CuotaMensual.Estado.PAGADA
    CuotaMensual.objects.filter(pk=cuota.pk).update(monto_pagado=pagado, saldo=saldo, estado=estado)
    cuota.monto_pagado = pagado
    cuota.saldo = saldo
    cuota.estado = estado
    return cuota


def obtener_saldo_responsable(responsable, colonia=None):
    cuotas = responsable.cuotas.exclude(estado=CuotaMensual.Estado.ANULADA)
    if colonia is not None:
        cuotas = cuotas.filter(colonia=colonia)
    return cuotas.aggregate(total=Sum("saldo"))["total"] or Decimal("0.00")


def obtener_saldo_casa(casa):
    """Compatibilidad de interfaz: el saldo pertenece a la persona, la casa solo da el contexto."""
    if not casa.responsable_actual_id:
        return Decimal("0.00")
    return obtener_saldo_responsable(casa.responsable_actual, casa.colonia)
