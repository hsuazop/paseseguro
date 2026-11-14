import calendar
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone

from colonias.models import Casa, Colonia
from core.models import registrar_auditoria
from facturacion.models import AplicacionPago, CuotaMensual, TarifaColonia, TarifaEspecialCasa


CENTAVOS = Decimal("0.01")


@transaction.atomic
def asegurar_cuota(*, casa, anio, mes, usuario=None):
    """One monthly charge per person; never rewrite an existing charge or payment."""
    fecha = date(anio, mes, 1)
    Colonia.objects.select_for_update().get(pk=casa.colonia_id)
    if not casa.activa or not casa.responsable_actual_id or not casa.responsable_actual.activo:
        raise ValidationError("La casa debe tener un responsable activo para registrar su cuota.")
    cuota = CuotaMensual.objects.filter(
        responsable=casa.responsable_actual, colonia=casa.colonia, anio=anio, mes=mes,
    ).first()
    if cuota:
        return cuota
    # Multiple homes belonging to one person use the same canonical home as batch generation.
    casa = Casa.objects.filter(
        colonia=casa.colonia, responsable_actual=casa.responsable_actual, activa=True,
    ).select_related("colonia", "responsable_actual").order_by("pk").first()
    monto = obtener_monto_cuota(casa, anio, mes)
    cuota = CuotaMensual.objects.create(
        casa=casa, responsable=casa.responsable_actual, colonia=casa.colonia,
        anio=anio, mes=mes, monto_original=monto, saldo=monto,
        fecha_vencimiento=fecha.replace(day=calendar.monthrange(anio, mes)[1]),
    )
    registrar_auditoria(usuario=usuario, accion="GENERACION_CUOTAS", objeto=cuota,
                        descripcion=f"Cuota de {cuota.periodo} generada automáticamente con tarifa L {monto:.2f}.")
    return cuota


@transaction.atomic
def definir_tarifa(*, colonia, monto, anio, mes, usuario):
    inicio = date(anio, mes, 1)
    if inicio < timezone.localdate().replace(day=1):
        raise ValidationError("El cambio de tarifa debe iniciar este mes o en un mes futuro para conservar el historial.")
    Colonia.objects.select_for_update().get(pk=colonia.pk)
    if TarifaColonia.objects.filter(colonia=colonia, activa=True, fecha_inicio__gt=inicio).exists():
        raise ValidationError("Ya hay una tarifa programada después de este mes. Revise su vigencia antes de cambiarla.")
    anteriores = TarifaColonia.objects.filter(colonia=colonia, activa=True).filter(
        Q(fecha_fin__isnull=True) | Q(fecha_fin__gte=inicio),
    )
    for anterior in anteriores:
        if anterior.fecha_inicio >= inicio:
            anterior.activa = False
        else:
            anterior.fecha_fin = inicio - timedelta(days=1)
        anterior.save()
    tarifa = TarifaColonia(colonia=colonia, monto=monto, fecha_inicio=inicio)
    tarifa.full_clean()
    tarifa.save()
    registrar_auditoria(usuario=usuario, accion="CREACION_TARIFA", objeto=tarifa,
                        descripcion=f"Cuota mensual automática de L {monto:.2f} desde {mes:02d}/{anio}.")
    hoy = timezone.localdate()
    generar_cuotas_mes(colonia=colonia, anio=hoy.year, mes=hoy.month, usuario=usuario)
    return tarifa


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
    Colonia.objects.select_for_update().get(pk=colonia.pk)
    existentes_ids = set(CuotaMensual.objects.filter(colonia=colonia, anio=anio, mes=mes).values_list("responsable_id", flat=True))

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
        if responsable.pk in existentes_ids:
            existentes += 1
            continue
        try:
            asegurar_cuota(casa=casa, anio=anio, mes=mes, usuario=usuario)
        except ValidationError as exc:
            errores.extend(exc.messages)
            continue
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
