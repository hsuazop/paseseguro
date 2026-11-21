from decimal import Decimal
from urllib.parse import urlencode

from django.contrib import messages
from django.db import transaction
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache

from accounts.permissions import ROLES_FINANCIEROS, colonia_actual, colonias_permitidas, puede_elegir_colonia, roles_requeridos
from core.models import registrar_auditoria
from core.pagination import paginar
from .gastos_forms import GastoMensualForm
from .models import AplicacionPago, CuotaMensual, GastoMensual


def periodo(request):
    hoy = timezone.localdate()
    try:
        anio, mes = int(request.GET.get("anio", hoy.year)), int(request.GET.get("mes", hoy.month))
        if not 2020 <= anio <= 2100 or not 1 <= mes <= 12:
            raise ValueError
    except (ValueError, TypeError):
        anio, mes = hoy.year, hoy.month
    return anio, mes


def contexto_periodo(request):
    colonias, colonia = colonia_actual(request)
    anio, mes = periodo(request)
    return {"colonias": colonias, "colonia": colonia, "anio": anio, "mes": mes,
            "meses": CuotaMensual.MESES, "elegir_colonia": puede_elegir_colonia(request.user)}


@roles_requeridos(*ROLES_FINANCIEROS)
@never_cache
def lista(request):
    contexto = contexto_periodo(request)
    gastos = GastoMensual.objects.filter(colonia=contexto["colonia"], anio=contexto["anio"], mes=contexto["mes"]).select_related("registrado_por")
    contexto["total_gastos"] = gastos.aggregate(total=Sum("monto"))["total"] or Decimal("0.00")
    contexto["page_obj"] = paginar(request, gastos)
    return render(request, "facturacion/gastos_lista.html", contexto)


@roles_requeridos(*ROLES_FINANCIEROS)
@never_cache
def formulario(request, pk=None):
    anio, mes = periodo(request)
    # Lock edits so the audit trail records the exact previous values.
    with transaction.atomic():
        gasto = get_object_or_404(GastoMensual.objects.select_for_update(), pk=pk,
            colonia__in=colonias_permitidas(request.user)) if pk else GastoMensual(registrado_por=request.user)
        anteriores = {"tipo": gasto.tipo, "anio": gasto.anio, "mes": gasto.mes,
                      "monto": str(gasto.monto), "descripcion": gasto.descripcion} if pk else None
        form = GastoMensualForm(request.POST if request.method == "POST" else None,
            instance=gasto, usuario=request.user, initial={} if pk else {"anio": anio, "mes": mes, "colonia": request.GET.get("colonia")})
        if request.method == "POST" and form.is_valid():
            gasto = form.save()
            nuevos = {"tipo": gasto.tipo, "anio": gasto.anio, "mes": gasto.mes,
                      "monto": str(gasto.monto), "descripcion": gasto.descripcion}
            registrar_auditoria(usuario=request.user, accion="EDITAR_GASTO" if pk else "CREAR_GASTO", objeto=gasto,
                descripcion=f"Gasto de {gasto.periodo} por L {gasto.monto:.2f}.", anteriores=anteriores, nuevos=nuevos)
            messages.success(request, "Gasto guardado correctamente.")
            return redirect(reverse("gastos_lista") + "?" + urlencode({"colonia": gasto.colonia_id, "anio": gasto.anio, "mes": gasto.mes}))
    return render(request, "facturacion/gasto_form.html", {"form": form, "gasto": gasto})


@roles_requeridos(*ROLES_FINANCIEROS)
@never_cache
def resumen(request):
    contexto = contexto_periodo(request)
    colonia, anio, mes = contexto["colonia"], contexto["anio"], contexto["mes"]
    ingresos = AplicacionPago.objects.filter(cuota_mensual__colonia=colonia, cuota_mensual__anio=anio,
        pago__anulado=False).exclude(cuota_mensual__estado=CuotaMensual.Estado.ANULADA)
    gastos = GastoMensual.objects.filter(colonia=colonia, anio=anio)
    ingresos_mes = dict(ingresos.order_by().values_list("cuota_mensual__mes").annotate(total=Sum("monto_aplicado")))
    gastos_mes = dict(gastos.order_by().values_list("mes").annotate(total=Sum("monto")))
    filas = []
    for numero, nombre in CuotaMensual.MESES:
        recaudado = ingresos_mes.get(numero, Decimal("0.00"))
        gastado = gastos_mes.get(numero, Decimal("0.00"))
        filas.append({"mes": numero, "nombre": nombre, "recaudado": recaudado, "gastos": gastado, "saldo": recaudado - gastado})
    detalle = gastos.filter(mes=mes).order_by().values("tipo").annotate(total=Sum("monto"))
    tipos = dict(GastoMensual.Tipo.choices)
    contexto.update(filas[mes - 1])
    contexto.update({"filas": filas, "detalle_gastos": [{"tipo": tipos.get(g["tipo"], g["tipo"]), "total": g["total"]} for g in detalle],
        "recaudado_anio": sum(ingresos_mes.values(), Decimal("0.00")), "gastos_anio": sum(gastos_mes.values(), Decimal("0.00"))})
    contexto["saldo_anio"] = contexto["recaudado_anio"] - contexto["gastos_anio"]
    return render(request, "facturacion/resumen_contable.html", contexto)
