from datetime import date
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Sum
from django.shortcuts import redirect, render

from accounts.models import User
from accounts.permissions import colonias_permitidas
from facturacion.models import AplicacionPago, CuotaMensual


def _periodo_seleccionado(request):
    hoy = date.today()
    try:
        anio = int(request.GET.get("anio", hoy.year))
    except (TypeError, ValueError):
        anio = hoy.year
    try:
        mes = int(request.GET.get("mes", hoy.month))
    except (TypeError, ValueError):
        mes = hoy.month
    if not 2020 <= anio <= 2100:
        anio = hoy.year
    if not 1 <= mes <= 12:
        mes = hoy.month
    return anio, mes


def _metricas_periodo(cuotas):
    esperado = cuotas.aggregate(total=Sum("monto_original"))["total"] or Decimal("0")
    cobrado = AplicacionPago.objects.filter(
        cuota_mensual__in=cuotas,
        pago__anulado=False,
    ).aggregate(total=Sum("monto_aplicado"))["total"] or Decimal("0")
    pendiente = cuotas.aggregate(total=Sum("saldo"))["total"] or Decimal("0")
    porcentaje = (cobrado / esperado * 100) if esperado else Decimal("0")
    return esperado, cobrado, pendiente, porcentaje


@login_required
def dashboard(request):
    if request.user.rol == User.Rol.RESIDENTE and not request.user.es_superadmin:
        return redirect("mi_cuenta")
    if request.user.rol == User.Rol.GUARDIA and not request.user.es_superadmin:
        return redirect("dashboard_guardia")

    anio, mes = _periodo_seleccionado(request)
    colonias = colonias_permitidas(request.user).filter(activa=True)
    colonia_id = request.GET.get("colonia") or request.session.get("colonia_actual")
    colonia = colonias.filter(pk=colonia_id).first() if colonia_id else colonias.first()
    cuentas = []
    aplicaciones_mes = []
    if colonia:
        request.session["colonia_actual"] = colonia.pk
        cuotas = CuotaMensual.objects.filter(colonia=colonia, anio=anio, mes=mes).exclude(
            estado=CuotaMensual.Estado.ANULADA
        )
        esperado, cobrado, pendiente, porcentaje = _metricas_periodo(cuotas)

        casas_por_responsable = {}
        casas_activas = colonia.casas.filter(
            activa=True,
            responsable_actual__isnull=False,
        ).select_related("responsable_actual").order_by("codigo")
        for casa in casas_activas:
            casas_por_responsable.setdefault(casa.responsable_actual_id, casa)

        responsable_ids = list(casas_por_responsable)
        cuotas_mes_por_responsable = {
            cuota.responsable_id: cuota
            for cuota in cuotas.select_related("responsable")
        }
        mora_por_responsable = {
            fila["responsable_id"]: fila
            for fila in CuotaMensual.objects.filter(
                colonia=colonia,
                responsable_id__in=responsable_ids,
                saldo__gt=0,
            ).filter(
                Q(anio__lt=anio) | Q(anio=anio, mes__lte=mes)
            ).exclude(
                estado=CuotaMensual.Estado.ANULADA
            ).values("responsable_id").annotate(
                meses_mora=Count("id"),
                saldo_mora=Sum("saldo"),
            )
        }

        for responsable_id, casa in casas_por_responsable.items():
            mora = mora_por_responsable.get(responsable_id, {})
            meses_mora = mora.get("meses_mora", 0)
            cuentas.append({
                "casa": casa,
                "responsable": casa.responsable_actual,
                "cuota_mes": cuotas_mes_por_responsable.get(responsable_id),
                "meses_mora": meses_mora,
                "saldo_mora": mora.get("saldo_mora", Decimal("0")),
                "al_dia": meses_mora == 0,
            })

        aplicaciones_mes = AplicacionPago.objects.filter(
            cuota_mensual__in=cuotas,
            pago__anulado=False,
        ).select_related(
            "pago",
            "pago__responsable",
            "pago__casa",
            "cuota_mensual",
        ).order_by("-pago__fecha_pago", "-pago_id")[:100]
        casas = len(casas_por_responsable)
        pagadas = cuotas.filter(estado=CuotaMensual.Estado.PAGADA).values(
            "responsable_id"
        ).distinct().count()
        parciales_pendientes = sum(1 for cuenta in cuentas if not cuenta["al_dia"])
    else:
        esperado = cobrado = pendiente = porcentaje = Decimal("0")
        casas = pagadas = parciales_pendientes = 0
    context = {
        "colonias": colonias,
        "colonia": colonia,
        "anio": anio,
        "mes": mes,
        "meses": CuotaMensual.MESES,
        "esperado": esperado,
        "cobrado": cobrado,
        "pendiente": pendiente,
        "porcentaje": porcentaje,
        "casas": casas,
        "pagadas": pagadas,
        "pendientes_count": parciales_pendientes,
        "cuentas": cuentas,
        "aplicaciones_mes": aplicaciones_mes,
    }
    return render(request, "core/dashboard.html", context)


@login_required
def dashboard_financiero(request):
    if request.user.rol == User.Rol.RESIDENTE and not request.user.es_superadmin:
        return redirect("mi_cuenta")
    if request.user.rol == User.Rol.GUARDIA and not request.user.es_superadmin:
        return redirect("dashboard_guardia")

    anio, mes = _periodo_seleccionado(request)
    colonias = colonias_permitidas(request.user).filter(activa=True)
    resumen = []
    total_esperado = Decimal("0")
    total_cobrado = Decimal("0")
    total_pendiente = Decimal("0")

    for colonia in colonias:
        cuotas = CuotaMensual.objects.filter(
            colonia=colonia,
            anio=anio,
            mes=mes,
        ).exclude(estado=CuotaMensual.Estado.ANULADA)
        esperado, cobrado, pendiente, porcentaje = _metricas_periodo(cuotas)
        personas = cuotas.values("responsable_id").distinct().count()
        pagadas = cuotas.filter(estado=CuotaMensual.Estado.PAGADA).values(
            "responsable_id"
        ).distinct().count()
        resumen.append({
            "colonia": colonia,
            "esperado": esperado,
            "cobrado": cobrado,
            "pendiente": pendiente,
            "porcentaje": porcentaje,
            "personas": personas,
            "pagadas": pagadas,
            "pendientes": max(personas - pagadas, 0),
        })
        total_esperado += esperado
        total_cobrado += cobrado
        total_pendiente += pendiente

    porcentaje_total = (
        total_cobrado / total_esperado * 100
        if total_esperado else Decimal("0")
    )
    return render(request, "core/dashboard_financiero.html", {
        "anio": anio,
        "mes": mes,
        "meses": CuotaMensual.MESES,
        "resumen": resumen,
        "esperado": total_esperado,
        "cobrado": total_cobrado,
        "pendiente": total_pendiente,
        "porcentaje": porcentaje_total,
    })
