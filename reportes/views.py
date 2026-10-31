from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal
from io import BytesIO

from django.db.models import Count, Q, Sum
from django.http import HttpResponse
from django.shortcuts import render

from accounts.permissions import ROLES_FINANCIEROS, colonias_permitidas, roles_requeridos
from colonias.models import Casa
from facturacion.models import AplicacionPago, CuotaMensual, Pago
from residentes.models import Responsable


def _filtros_periodo(request, cuotas):
    colonia_id = request.GET.get("colonia", "")
    anio = request.GET.get("anio", "")
    mes = request.GET.get("mes", "")
    if colonia_id:
        cuotas = cuotas.filter(colonia_id=colonia_id)
    if anio:
        cuotas = cuotas.filter(anio=anio)
    if mes:
        cuotas = cuotas.filter(mes=mes)
    return cuotas


@roles_requeridos(*ROLES_FINANCIEROS)
def morosidad(request):
    colonia_id = request.GET.get("colonia", "")
    cuentas = _cuentas_morosas(request.user, colonia_id)
    context = {"cuentas": cuentas, "colonias": colonias_permitidas(request.user), "colonia_id": colonia_id}
    return render(request, "reportes/morosidad.html", context)


def _cuentas_morosas(user, colonia_id=""):
    colonias = colonias_permitidas(user)
    if colonia_id:
        colonias = colonias.filter(pk=colonia_id)
    resultados = []
    for colonia in colonias:
        responsables = Responsable.objects.filter(
            cuotas__colonia=colonia,
            cuotas__saldo__gt=0,
        ).annotate(
            saldo_total=Sum(
                "cuotas__saldo",
                filter=Q(cuotas__colonia=colonia)
                & Q(cuotas__saldo__gt=0)
                & ~Q(cuotas__estado=CuotaMensual.Estado.ANULADA),
            ),
            meses_pendientes=Count(
                "cuotas",
                filter=Q(cuotas__colonia=colonia)
                & Q(cuotas__saldo__gt=0)
                & ~Q(cuotas__estado=CuotaMensual.Estado.ANULADA),
            ),
        ).distinct()
        for responsable in responsables:
            residencia = responsable.casas_actuales.filter(colonia=colonia, activa=True).order_by("pk").first()
            responsable.colonia_cuenta = colonia
            responsable.residencia_id = residencia.pk if residencia else None
            responsable.residencia_codigo = residencia.codigo if residencia else ""
            resultados.append(responsable)
    return sorted(resultados, key=lambda item: (item.colonia_cuenta.nombre, item.nombre_completo))


def _datos_recaudacion(cuotas):
    grupos = defaultdict(lambda: {"esperado": Decimal("0"), "pendiente": Decimal("0"), "cuota_ids": []})
    for cuota in cuotas.select_related("colonia"):
        clave = (cuota.colonia_id, cuota.colonia.nombre, cuota.anio, cuota.mes, cuota.get_mes_display())
        grupos[clave]["esperado"] += cuota.monto_original
        grupos[clave]["pendiente"] += cuota.saldo
        grupos[clave]["cuota_ids"].append(cuota.pk)
    resultados = []
    for clave, datos in grupos.items():
        cobrado = AplicacionPago.objects.filter(
            cuota_mensual_id__in=datos["cuota_ids"], pago__anulado=False,
        ).aggregate(total=Sum("monto_aplicado"))["total"] or Decimal("0")
        esperado = datos["esperado"]
        resultados.append({
            "colonia_id": clave[0], "colonia": clave[1], "anio": clave[2], "mes": clave[3], "mes_nombre": clave[4],
            "esperado": esperado, "cobrado": cobrado, "pendiente": datos["pendiente"],
            "porcentaje": cobrado / esperado * 100 if esperado else Decimal("0"),
        })
    return sorted(resultados, key=lambda x: (x["anio"], x["mes"], x["colonia"]), reverse=True)


@roles_requeridos(*ROLES_FINANCIEROS)
def recaudacion(request):
    cuotas = CuotaMensual.objects.filter(colonia__in=colonias_permitidas(request.user)).exclude(
        estado=CuotaMensual.Estado.ANULADA
    )
    cuotas = _filtros_periodo(request, cuotas)
    datos = _datos_recaudacion(cuotas)
    return render(request, "reportes/recaudacion.html", {
        "datos": datos, "colonias": colonias_permitidas(request.user), "meses": CuotaMensual.MESES,
        "filtros": request.GET,
    })


def _pagos_filtrados(request):
    pagos = Pago.objects.filter(colonia__in=colonias_permitidas(request.user)).select_related(
        "casa", "colonia", "responsable", "usuario_que_registra",
    )
    colonia = request.GET.get("colonia", "")
    desde = request.GET.get("desde", "")
    hasta = request.GET.get("hasta", "")
    casa = request.GET.get("casa", "").strip()
    metodo = request.GET.get("metodo", "")
    usuario = request.GET.get("usuario", "").strip()
    if colonia:
        pagos = pagos.filter(colonia_id=colonia)
    if desde:
        pagos = pagos.filter(fecha_pago__gte=desde)
    if hasta:
        pagos = pagos.filter(fecha_pago__lte=hasta)
    if casa:
        pagos = pagos.filter(Q(casa__codigo__icontains=casa) | Q(responsable__nombre_completo__icontains=casa))
    if metodo:
        pagos = pagos.filter(metodo_pago=metodo)
    if usuario:
        pagos = pagos.filter(Q(usuario_que_registra__username__icontains=usuario) | Q(usuario_que_registra__first_name__icontains=usuario))
    return pagos


@roles_requeridos(*ROLES_FINANCIEROS)
def historial_pagos(request):
    return render(request, "reportes/historial_pagos.html", {
        "pagos": _pagos_filtrados(request)[:1000], "colonias": colonias_permitidas(request.user),
        "metodos": Pago.Metodo.choices, "filtros": request.GET,
    })


def _respuesta_excel(nombre, encabezados, filas):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill

    wb = Workbook()
    ws = wb.active
    ws.title = "Reporte"
    ws.append(encabezados)
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="163B65")
    for fila in filas:
        ws.append(fila)
    for column in ws.columns:
        letter = column[0].column_letter
        ws.column_dimensions[letter].width = min(max(len(str(c.value or "")) for c in column) + 2, 40)
    output = BytesIO()
    wb.save(output)
    response = HttpResponse(
        output.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="{nombre}.xlsx"'
    return response


@roles_requeridos(*ROLES_FINANCIEROS)
def exportar_morosidad_excel(request):
    cuentas = _cuentas_morosas(request.user, request.GET.get("colonia", ""))
    filas = [
        [c.colonia_cuenta.nombre, c.residencia_codigo or "", c.nombre_completo, c.telefono, c.meses_pendientes, c.saldo_total]
        for c in cuentas
    ]
    return _respuesta_excel("morosidad", ["Colonia", "Casa", "Responsable", "Telefono", "Meses pendientes", "Saldo"], filas)


@roles_requeridos(*ROLES_FINANCIEROS)
def exportar_recaudacion_excel(request):
    cuotas = _filtros_periodo(request, CuotaMensual.objects.filter(
        colonia__in=colonias_permitidas(request.user)
    ).exclude(estado=CuotaMensual.Estado.ANULADA))
    datos = _datos_recaudacion(cuotas)
    filas = [[d["colonia"], d["mes_nombre"], d["anio"], d["esperado"], d["cobrado"], d["pendiente"], d["porcentaje"] / 100] for d in datos]
    return _respuesta_excel("recaudacion", ["Colonia", "Mes", "Año", "Esperado", "Cobrado", "Pendiente", "Porcentaje"], filas)


@roles_requeridos(*ROLES_FINANCIEROS)
def exportar_pagos_excel(request):
    filas = [
        [p.numero_recibo, p.fecha_pago, p.colonia.nombre, p.casa.codigo, p.responsable.nombre_completo, p.monto_total, p.get_metodo_pago_display(), p.usuario_que_registra.nombre_completo, "Anulado" if p.anulado else "Activo"]
        for p in _pagos_filtrados(request)
    ]
    return _respuesta_excel("historial_pagos", ["Recibo", "Fecha", "Colonia", "Casa", "Responsable", "Monto", "Metodo", "Registrado por", "Estado"], filas)


@roles_requeridos(*ROLES_FINANCIEROS)
def reporte_pdf(request, tipo):
    from .pdf import generar_reporte_pdf

    if tipo == "morosidad":
        cuentas = _cuentas_morosas(request.user, request.GET.get("colonia", ""))
        titulo = "Reporte de morosidad"
        encabezados = ["Colonia", "Casa", "Responsable", "Telefono", "Meses", "Saldo"]
        filas = [[
            c.colonia_cuenta.nombre, c.residencia_codigo or "", c.nombre_completo,
            c.telefono, c.meses_pendientes, f"L {c.saldo_total:,.2f}",
        ] for c in cuentas]
    elif tipo == "recaudacion":
        cuotas = _filtros_periodo(request, CuotaMensual.objects.filter(colonia__in=colonias_permitidas(request.user)))
        titulo = "Reporte de recaudacion"
        encabezados = ["Colonia", "Periodo", "Esperado", "Cobrado", "Pendiente", "Porcentaje"]
        filas = [[
            d["colonia"], f'{d["mes_nombre"]} {d["anio"]}', f'L {d["esperado"]:,.2f}',
            f'L {d["cobrado"]:,.2f}', f'L {d["pendiente"]:,.2f}', f'{d["porcentaje"]:.1f}%',
        ] for d in _datos_recaudacion(cuotas)]
    else:
        titulo = "Historial de pagos"
        encabezados = ["Recibo", "Fecha", "Colonia", "Casa", "Responsable", "Metodo", "Monto"]
        filas = [[
            p.numero_recibo, p.fecha_pago.strftime("%d/%m/%Y"), p.colonia.nombre, p.casa.codigo,
            p.responsable.nombre_completo, p.get_metodo_pago_display(), f"L {p.monto_total:,.2f}",
        ] for p in _pagos_filtrados(request)]
    pdf = generar_reporte_pdf(titulo=titulo, encabezados=encabezados, filas=filas)
    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{tipo}.pdf"'
    return response
