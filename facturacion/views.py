from datetime import date
from decimal import Decimal
import logging
from django.conf import settings

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q, Sum
from django.db import DatabaseError, IntegrityError, transaction
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.decorators.cache import never_cache
from django.http import HttpResponse
from django.urls import reverse
from django.shortcuts import get_object_or_404, redirect, render

from accesos.forms import VehiculoForm
from accounts.models import User
from accounts.permissions import ocultar_listado_pagos
from accounts.permissions import ROLES_GESTION, ROLES_FINANCIEROS, colonia_actual, filtro_colonia, colonias_permitidas, roles_requeridos
from residentes.forms import RegistrarResidenteForm
from colonias.models import Casa
from core.models import registrar_auditoria
from core.pagination import paginar

from .forms import (
    AnularPagoForm,
    ComprobantePagoForm,
    CuotaReferenciaForm,
    CuentaPagoColoniaForm,
    GenerarCuotasForm,
    PagoForm,
    PagoEfectivoForm,
    RevisarComprobanteForm,
    TarifaColoniaForm,
    TarifaEspecialForm,
)
from .models import AplicacionPago, ComprobanteCuota, ComprobantePago, CuentaPagoColonia, CuotaMensual, Pago, TarifaColonia, TarifaEspecialCasa
from .services import anular_pago, generar_cuotas_mes, registrar_pago
from .services.cuotas import asegurar_cuota, definir_tarifa


def _pagos_permitidos(user):
    if user.es_superadmin:
        return Pago.objects.all()
    if user.rol == User.Rol.RESIDENTE:
        try:
            return Pago.objects.filter(responsable=user.responsable)
        except Exception:
            return Pago.objects.none()
    return Pago.objects.filter(colonia__in=colonias_permitidas(user))


def _colonia_financiera_actual(request):
    return colonia_actual(request)


@roles_requeridos(*ROLES_FINANCIEROS)
def tesoreria(request):
    """Vista operativa: una persona por fila y el estado de vigilancia del período."""
    hoy = date.today()
    try:
        anio = int(request.GET.get("anio", hoy.year))
        mes = int(request.GET.get("mes", hoy.month))
    except (TypeError, ValueError):
        anio, mes = hoy.year, hoy.month
    if not 2020 <= anio <= 2100:
        anio = hoy.year
    if not 1 <= mes <= 12:
        mes = hoy.month

    colonias, colonia = _colonia_financiera_actual(request)
    filas = []
    pagadas = pendientes = por_validar = 0
    esperado = recaudado = saldo_periodo = Decimal("0.00")
    porcentaje = Decimal("0.00")
    aplicaciones = []
    if colonia:
        casas = list(
            Casa.objects.filter(colonia=colonia, activa=True, responsable_actual__isnull=False)
            .select_related("responsable_actual")
            .order_by("codigo")
        )
        cuotas = CuotaMensual.objects.filter(
            colonia=colonia, anio=anio, mes=mes
        ).exclude(estado=CuotaMensual.Estado.ANULADA)
        cuotas_por_responsable = {cuota.responsable_id: cuota for cuota in cuotas}
        totales = cuotas.aggregate(esperado=Sum("monto_original"), saldo=Sum("saldo"))
        esperado = totales["esperado"] or Decimal("0.00")
        saldo_periodo = totales["saldo"] or Decimal("0.00")
        aplicaciones = AplicacionPago.objects.filter(
            cuota_mensual__in=cuotas, pago__anulado=False,
        ).select_related(
            "pago", "pago__casa", "pago__responsable", "pago__comprobante_origen",
        ).order_by("pago__fecha_pago", "pago_id", "pk")
        recaudado = aplicaciones.aggregate(total=Sum("monto_aplicado"))["total"] or Decimal("0.00")
        porcentaje = recaudado / esperado * 100 if esperado else Decimal("0.00")
        comprobantes = (
            ComprobantePago.objects.filter(
                colonia=colonia,
                cuotas__anio=anio,
                cuotas__mes=mes,
            )
            .select_related("pago")
            .prefetch_related("cuotas")
            .order_by("-created_at")
            .distinct()
        )
        comprobante_por_responsable = {}
        for comprobante in comprobantes:
            previo = comprobante_por_responsable.get(comprobante.responsable_id)
            if previo is None or (previo.estado != ComprobantePago.Estado.PENDIENTE and comprobante.estado == ComprobantePago.Estado.PENDIENTE):
                comprobante_por_responsable[comprobante.responsable_id] = comprobante

        for casa in casas:
            cuota = cuotas_por_responsable.get(casa.responsable_actual_id)
            comprobante = comprobante_por_responsable.get(casa.responsable_actual_id)
            if cuota and cuota.estado == CuotaMensual.Estado.PAGADA:
                estado = "PAGADA"
                pagadas += 1
            elif comprobante and comprobante.estado == ComprobantePago.Estado.PENDIENTE:
                estado = "POR_VALIDAR"
                por_validar += 1
            else:
                estado = "PENDIENTE"
                pendientes += 1
            filas.append({
                "casa": casa,
                "responsable": casa.responsable_actual,
                "cuota": cuota,
                "comprobante": comprobante,
                "estado": estado,
            })

    return render(request, "facturacion/tesoreria.html", {
        "colonia_fija": request.user.rol == User.Rol.TESORERO and not request.user.es_superadmin,
        "colonias": colonias,
        "colonia": colonia,
        "anio": anio,
        "mes": mes,
        "meses": CuotaMensual.MESES,
        "filas": filas,
        "pagadas": pagadas,
        "pendientes": pendientes,
        "por_validar": por_validar,
        "esperado": esperado,
        "recaudado": recaudado,
        "saldo_periodo": saldo_periodo,
        "porcentaje": porcentaje,
        "aplicaciones": aplicaciones,
    })


@roles_requeridos(*ROLES_FINANCIEROS)
def pago_efectivo(request):
    from .services.efectivo import registrar_efectivo

    _, colonia = _colonia_financiera_actual(request)
    if not colonia:
        messages.warning(request, "No tiene una residencial activa asignada.")
        return redirect("tesoreria")
    if request.method == "GET" and request.GET.get("tipo") == "nuevo":
        return redirect("registrar_residente")
    hoy = timezone.localdate()
    form = PagoEfectivoForm(
        request.POST if request.method == "POST" else None, colonia=colonia,
        initial={"casa": request.GET.get("casa"),
                 "mes": request.GET.get("mes", hoy.month), "anio": request.GET.get("anio", hoy.year),
                 "fecha_pago": hoy},
    )
    if request.method == "POST" and request.POST.get("tipo") == "nuevo":
        form.add_error(None, "Use Registrar Residente para dar de alta al vecino.")
    elif request.method == "POST" and form.is_valid():
        try:
            pago = registrar_efectivo(colonia=colonia, usuario=request.user, datos=form.cleaned_data)
        except ValidationError as exc:
            for error in exc.messages:
                form.add_error(None, error)
        except IntegrityError:
            form.add_error(None, "El pago ya fue registrado. Revise los datos antes de intentar de nuevo.")
        else:
            messages.success(request, f"Efectivo registrado. Recibo {pago.numero_recibo}.")
            return redirect("recibo_detalle", pk=pago.pk)
    return render(request, "facturacion/pago_efectivo.html", {"form": form, "colonia": colonia})


@roles_requeridos(*ROLES_FINANCIEROS)
@never_cache
def registrar_residente(request):
    from residentes.services import registrar_residente as crear_residente

    _, colonia = _colonia_financiera_actual(request)
    if not colonia:
        messages.warning(request, "No tiene una residencial activa asignada.")
        return redirect("tesoreria")
    datos = request.POST if request.method == "POST" else None
    form = RegistrarResidenteForm(datos, colonia=colonia)
    agregar_vehiculo = request.method == "POST" and request.POST.get("agregar_vehiculo") == "1"
    form_vehiculo = VehiculoForm(datos if agregar_vehiculo else None, prefix="vehiculo")
    clave_sesion = f"alta_residente_{colonia.pk}_"
    if form.is_valid() and (not agregar_vehiculo or form_vehiculo.is_valid()):
        vehiculo = form_vehiculo.save(commit=False) if agregar_vehiculo else None
        try:
            casa, temporal = crear_residente(
                colonia=colonia, usuario=request.user, datos=form.cleaned_data, vehiculo=vehiculo,
            )
        except ValidationError as exc:
            for error in exc.messages:
                form.add_error(None, error)
        except IntegrityError:
            form.add_error(None, "Revise si la identidad, la casa o la placa ya está registrada.")
        else:
            request.session[f"{clave_sesion}{casa.pk}"] = {
                "usuario": casa.responsable_actual.usuario.username, "password": temporal,
                "nombre": casa.responsable_actual.nombre_completo, "casa_id": casa.pk,
                "placa": vehiculo.placa if vehiculo else "",
            }
            return redirect(reverse("registrar_residente", query={"alta": casa.pk}))
    return render(request, "facturacion/registrar_residente.html", {
        "form": form, "colonia": colonia,
        "form_vehiculo": form_vehiculo, "agregar_vehiculo": agregar_vehiculo,
        "alta": request.session.pop(clave_sesion + request.GET["alta"], None)
                if request.method == "GET" and "alta" in request.GET else None,
    })


@roles_requeridos(*ROLES_GESTION)
def tarifas_lista(request):
    tarifas = TarifaColonia.objects.filter(colonia__in=colonias_permitidas(request.user)).select_related("colonia")
    especiales = TarifaEspecialCasa.objects.filter(casa__colonia__in=colonias_permitidas(request.user)).select_related("casa", "casa__colonia")
    return render(request, "facturacion/tarifas_lista.html", {"tarifas": tarifas, "especiales": especiales})


@roles_requeridos(*ROLES_GESTION)
def tarifa_crear(request):
    hoy = timezone.localdate()
    form = CuotaReferenciaForm(request.POST or None, colonias_queryset=colonias_permitidas(request.user),
                              initial={"anio": hoy.year, "mes": hoy.month})
    if request.method == "POST" and form.is_valid():
        try:
            definir_tarifa(usuario=request.user, **form.cleaned_data)
        except ValidationError as exc:
            for error in exc.messages:
                form.add_error(None, error)
        else:
            messages.success(request, "Cuota de referencia guardada. Las cuotas mensuales se generan automáticamente; las anteriores conservan su monto y sus pagos.")
            return redirect("tarifas_lista")
    return render(request, "core/formulario.html", {"form": form, "titulo": "Definir cuota mensual de vigilancia", "volver": "tarifas_lista"})


@roles_requeridos(*ROLES_GESTION)
def tarifa_especial_crear(request):
    casas = Casa.objects.filter(colonia__in=colonias_permitidas(request.user), activa=True)
    form = TarifaEspecialForm(request.POST or None, casas_queryset=casas)
    if request.method == "POST" and form.is_valid():
        tarifa = form.save(commit=False)
        tarifa.usuario_que_autoriza = request.user
        tarifa.save()
        registrar_auditoria(
            usuario=request.user, accion="CREACION_TARIFA_ESPECIAL", objeto=tarifa,
            descripcion=f"Tarifa especial autorizada para {tarifa.casa}.",
            nuevos={"tipo": tarifa.tipo, "monto": str(tarifa.monto or ""), "porcentaje": str(tarifa.porcentaje or "")},
        )
        messages.success(request, "Tarifa especial creada correctamente.")
        return redirect("tarifas_lista")
    return render(request, "core/formulario.html", {"form": form, "titulo": "Nueva tarifa especial", "volver": "tarifas_lista"})


@roles_requeridos(*ROLES_FINANCIEROS)
def cuotas_lista(request):
    cuotas = CuotaMensual.objects.filter(colonia__in=colonias_permitidas(request.user)).select_related(
        "casa", "colonia", "responsable"
    )
    colonia_id = filtro_colonia(request)
    anio = request.GET.get("anio", "")
    mes = request.GET.get("mes", "")
    estado = request.GET.get("estado", "")
    if colonia_id:
        cuotas = cuotas.filter(colonia_id=colonia_id)
    if anio:
        cuotas = cuotas.filter(anio=anio)
    if mes:
        cuotas = cuotas.filter(mes=mes)
    if estado:
        cuotas = cuotas.filter(estado=estado)
    page_obj = paginar(request, cuotas)
    return render(request, "facturacion/cuotas_lista.html", {
        "cuotas": page_obj, "page_obj": page_obj, "colonias": colonias_permitidas(request.user), "meses": CuotaMensual.MESES,
        "estados": CuotaMensual.Estado.choices, "filtros": request.GET,
    })


@roles_requeridos(*ROLES_GESTION)
def cuotas_generar(request):
    form = GenerarCuotasForm(
        request.POST or None,
        colonias_queryset=colonias_permitidas(request.user).filter(activa=True),
        initial={"anio": date.today().year, "mes": date.today().month},
    )
    resultado = None
    if request.method == "POST" and form.is_valid():
        resultado = generar_cuotas_mes(usuario=request.user, **form.cleaned_data)
        if resultado["errores"]:
            for error in resultado["errores"]:
                messages.error(request, error)
        messages.success(
            request,
            f'{resultado["creadas"]} cuotas creadas. {resultado["existentes"]} ya existentes.',
        )
    return render(request, "facturacion/generar_cuotas.html", {"form": form, "resultado": resultado})


@roles_requeridos(*ROLES_FINANCIEROS)
def pagos_lista(request):
    if request.user.rol == User.Rol.TESORERO and ocultar_listado_pagos(
        request.user, colonias_permitidas(request.user).first()
    ):
        return redirect("tesoreria")
    pagos = _pagos_permitidos(request.user).select_related("casa", "colonia", "responsable", "usuario_que_registra")
    buscar = request.GET.get("q", "").strip()
    if buscar:
        pagos = pagos.filter(
            Q(numero_recibo__icontains=buscar) | Q(casa__codigo__icontains=buscar)
            | Q(responsable__nombre_completo__icontains=buscar) | Q(responsable__identidad__icontains=buscar)
        )
    page_obj = paginar(request, pagos)
    return render(request, "facturacion/pagos_lista.html", {"pagos": page_obj, "page_obj": page_obj, "buscar": buscar})


@roles_requeridos(*ROLES_FINANCIEROS)
def pago_nuevo(request):
    casas = Casa.objects.filter(colonia__in=colonias_permitidas(request.user), activa=True).select_related("colonia", "responsable_actual")
    casa_id = request.GET.get("casa") or request.POST.get("casa")
    casa = get_object_or_404(casas, pk=casa_id) if casa_id else None
    cuotas = (
        CuotaMensual.objects.filter(
            responsable=casa.responsable_actual,
            colonia=casa.colonia,
            saldo__gt=0,
        ).exclude(estado=CuotaMensual.Estado.ANULADA).order_by("anio", "mes")
        if casa and casa.responsable_actual_id
        else []
    )
    form = PagoForm(request.POST or None, initial={"fecha_pago": date.today()})
    if request.method == "POST" and casa and form.is_valid():
        aplicaciones = [
            {"cuota_id": cuota_id, "monto": request.POST.get(f"monto_{cuota_id}", "")}
            for cuota_id in request.POST.getlist("cuota_id")
        ]
        try:
            pago = registrar_pago(
                casa=casa,
                responsable=casa.responsable_actual,
                aplicaciones=aplicaciones,
                usuario=request.user,
                **form.cleaned_data,
            )
        except ValidationError as exc:
            for error in exc.messages:
                form.add_error(None, error)
        else:
            messages.success(request, f"Pago registrado. Recibo {pago.numero_recibo}.")
            return redirect("recibo_detalle", pk=pago.pk)
    return render(request, "facturacion/pago_nuevo.html", {
        "form": form, "casas": casas, "casa": casa, "cuotas": cuotas,
    })


def _pago_autorizado(request, pk):
    if not request.user.is_authenticated:
        raise PermissionDenied
    return get_object_or_404(_pagos_permitidos(request.user).select_related(
        "casa", "colonia", "responsable", "usuario_que_registra", "usuario_que_anula"
    ).prefetch_related("aplicaciones__cuota_mensual"), pk=pk)


def pago_detalle(request, pk):
    pago = _pago_autorizado(request, pk)
    return render(request, "facturacion/pago_detalle.html", {"pago": pago})


def recibo_detalle(request, pk):
    pago = _pago_autorizado(request, pk)
    alta = request.session.pop(f"alta_pago_{pago.pk}", None)
    if alta:
        response = render(request, "facturacion/efectivo_registrado.html", {"pago": pago, "alta": alta})
        response["Cache-Control"] = "no-store"
        return response
    return render(request, "facturacion/recibo.html", {"pago": pago, "publico": False})


@roles_requeridos(*ROLES_FINANCIEROS)
def pago_anular(request, pk):
    pago = _pago_autorizado(request, pk)
    form = AnularPagoForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            anular_pago(pago=pago, usuario=request.user, **form.cleaned_data)
        except ValidationError as exc:
            for error in exc.messages:
                form.add_error(None, error)
        else:
            messages.success(request, "Pago anulado y saldos recalculados.")
            return redirect("pago_detalle", pk=pago.pk)
    return render(request, "facturacion/anular_pago.html", {"pago": pago, "form": form})


def recibo_publico(request, token):
    pago = get_object_or_404(Pago.objects.select_related(
        "casa", "colonia", "responsable", "usuario_que_registra"
    ).prefetch_related("aplicaciones__cuota_mensual"), token_publico=token)
    return render(request, "facturacion/recibo.html", {"pago": pago, "publico": True})


def _pdf_recibo(request, pago):
    from .pdf import generar_recibo_pdf

    pdf = generar_recibo_pdf(pago)
    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{pago.numero_recibo}.pdf"'
    return response


def recibo_pdf(request, pk):
    return _pdf_recibo(request, _pago_autorizado(request, pk))


def recibo_publico_pdf(request, token):
    pago = get_object_or_404(Pago.objects.select_related(
        "casa", "colonia", "responsable", "usuario_que_registra"
    ).prefetch_related("aplicaciones__cuota_mensual"), token_publico=token)
    return _pdf_recibo(request, pago)


def _casa_residente(request, casa_id):
    from residentes.access import casa_del_residente

    if not request.user.is_authenticated:
        raise PermissionDenied
    if request.user.rol != User.Rol.RESIDENTE and not request.user.es_superadmin:
        raise PermissionDenied
    return casa_del_residente(request.user, casa_id)


def comprobantes_residente(request, casa_id):
    casa = _casa_residente(request, casa_id)
    comprobantes = ComprobantePago.objects.filter(
        responsable=casa.responsable_actual,
        colonia=casa.colonia,
        enviado_por=request.user,
    ).prefetch_related("cuotas")
    return render(request, "facturacion/comprobantes_residente.html", {"casa": casa, "comprobantes": comprobantes})


def comprobante_enviar(request, casa_id):
    casa = _casa_residente(request, casa_id)
    cuotas = CuotaMensual.objects.filter(
        responsable=casa.responsable_actual,
        colonia=casa.colonia,
        saldo__gt=0,
    ).exclude(estado=CuotaMensual.Estado.ANULADA).order_by("anio", "mes")
    form = ComprobantePagoForm(
        request.POST if request.method == "POST" else None,
        request.FILES if request.method == "POST" else None,
        cuotas_queryset=cuotas,
        casa=casa,
    )
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                cuota = asegurar_cuota(casa=casa, anio=form.cleaned_data["anio"], mes=form.cleaned_data["mes"], usuario=request.user)
                if cuota.estado in (CuotaMensual.Estado.PAGADA, CuotaMensual.Estado.ANULADA) or cuota.saldo < form.cleaned_data["monto"]:
                    raise ValidationError("El saldo de este período cambió. Revisa tu estado de cuenta antes de enviar el comprobante.")
                comprobante = form.save(commit=False)
                comprobante.casa = casa
                comprobante.colonia = casa.colonia
                comprobante.responsable = casa.responsable_actual
                comprobante.enviado_por = request.user
                comprobante.fecha_pago = timezone.localdate()
                comprobante.periodos_solicitados = [{"anio": cuota.anio, "mes": cuota.mes}]
                comprobante.full_clean(exclude=("cuotas",))
                comprobante.save()
                ComprobanteCuota.objects.create(comprobante=comprobante, cuota=cuota)
                registrar_auditoria(
                    usuario=request.user,
                    accion="ENVIO_COMPROBANTE",
                    objeto=comprobante,
                    descripcion=f"Comprobante por L {comprobante.monto:.2f} para {cuota.periodo} enviado.",
                )
        except ValidationError as exc:
            for error in exc.messages:
                form.add_error(None, error)
        except (OSError, DatabaseError):
            logging.getLogger(__name__).exception("No se pudo guardar el comprobante de casa %s", casa.pk)
            form.add_error(None, "No pudimos guardar tu comprobante. Adjunta el archivo nuevamente e intenta enviarlo. Si el problema continúa, comunícate con tesorería.")
        else:
            messages.success(request, f"Comprobante de {cuota.periodo} enviado para revisión.")
            return redirect("comprobantes_residente", casa_id=casa.pk)
    if request.method == "POST" and form.errors:
        form.fields["archivo"].help_text = "Vuelve a adjuntar tu comprobante para enviarlo. Formatos: JPG, PNG, WEBP o PDF. Máximo: 8 MB."
    return render(request, "facturacion/comprobante_enviar.html", {
        "casa": casa, "form": form,
    })


def cuenta_pago_residente(request, casa_id):
    casa = _casa_residente(request, casa_id)
    cuentas = CuentaPagoColonia.objects.filter(colonia=casa.colonia, activa=True)
    return render(request, "facturacion/cuentas_pago.html", {"casa": casa, "cuentas": cuentas})


@roles_requeridos(*ROLES_FINANCIEROS)
@never_cache
def comprobantes_gestion(request):
    comprobantes = ComprobantePago.objects.filter(
        colonia__in=colonias_permitidas(request.user), pago__isnull=True,
    ).exclude(estado=ComprobantePago.Estado.APROBADO).select_related(
        "casa", "colonia", "responsable", "enviado_por", "revisado_por", "pago"
    ).prefetch_related("cuotas")
    residentes = list(comprobantes.order_by("responsable__nombre_completo", "responsable_id").values(
        "responsable_id", "responsable__nombre_completo"
    ).distinct())
    residente = request.GET.get("residente", "")
    if residente:
        permitidos = {str(item["responsable_id"]) for item in residentes}
        comprobantes = comprobantes.filter(responsable_id=residente) if residente in permitidos else comprobantes.none()
    estado = request.GET.get("estado")
    if estado:
        comprobantes = comprobantes.filter(estado=estado)
    orden = "residente" if request.GET.get("orden") == "residente" else "antiguedad"
    comprobantes = comprobantes.order_by(
        *("responsable__nombre_completo", "responsable_id", "created_at", "pk")
        if orden == "residente" else ("created_at", "pk")
    )
    page_obj = paginar(request, comprobantes)
    for item in page_obj:
        cuotas = list(item.cuotas.all())
        initial = {'estado': 'APROBADO', 'comentario_revision': item.comentario_revision}
        if len(cuotas) == 1:
            initial.update(anio=cuotas[0].anio, mes=cuotas[0].mes)
        elif not cuotas and len(item.periodos_solicitados) == 1:
            initial.update(item.periodos_solicitados[0])
        item.revision_form = RevisarComprobanteForm(initial=initial, auto_id=f'id_{item.pk}_%s')
        for field in item.revision_form.fields.values():
            field.widget.attrs['form'] = f'revision-{item.pk}'
    return render(
        request,
        "facturacion/comprobantes_gestion.html",
        {"comprobantes": page_obj, "page_obj": page_obj,
         "estados": [(valor, etiqueta) for valor, etiqueta in ComprobantePago.Estado.choices
                     if valor != ComprobantePago.Estado.APROBADO],
         "residentes": residentes, "residente": residente, "orden": orden,
         "correo_configurado": bool(settings.EMAIL_HOST and settings.DEFAULT_FROM_EMAIL)},
    )


@roles_requeridos(*ROLES_FINANCIEROS)
@never_cache
def comprobante_revisar(request, pk):
    from .services.comprobantes import revisar_comprobante, enviar_estado_comprobante
    comprobante = get_object_or_404(ComprobantePago.objects.select_related('casa', 'colonia', 'responsable', 'enviado_por').prefetch_related('cuotas'),
                                   pk=pk, colonia__in=colonias_permitidas(request.user))
    cuotas = list(comprobante.cuotas.all())
    initial = {'estado': 'APROBADO', 'comentario_revision': comprobante.comentario_revision}
    if len(cuotas) == 1:
        initial.update(anio=cuotas[0].anio, mes=cuotas[0].mes)
    elif not cuotas and len(comprobante.periodos_solicitados) == 1:
        initial.update(comprobante.periodos_solicitados[0])
    form = RevisarComprobanteForm(request.POST if request.method == 'POST' else None, initial=initial)
    if request.method == 'POST' and form.is_valid():
        try:
            comprobante = revisar_comprobante(pk, form.cleaned_data, request.user)
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(request, 'Comprobante registrado y pago aplicado.' if comprobante.pago_id else 'Comprobante rechazado; no se registró un pago.')
            # The financial transaction is committed before contacting SMTP.
            resultado, mensaje = enviar_estado_comprobante(pk, request.user)
            (messages.warning if resultado == 'error' else messages.info)(request, mensaje)
            return redirect('comprobantes_gestion')
    return render(request, 'facturacion/comprobante_revisar.html', {'comprobante': comprobante, 'form': form})


@roles_requeridos(*ROLES_FINANCIEROS)
@require_POST
def comprobante_enviar_correo(request, pk):
    from .services.comprobantes import enviar_estado_comprobante
    get_object_or_404(ComprobantePago, pk=pk, colonia__in=colonias_permitidas(request.user))
    resultado, mensaje = enviar_estado_comprobante(pk, request.user)
    (messages.warning if resultado == 'error' else messages.info)(request, mensaje)
    return redirect('comprobantes_gestion')


@roles_requeridos(*ROLES_GESTION)
def cuenta_pago_crear(request):
    form = CuentaPagoColoniaForm(
        request.POST or None,
        colonias_queryset=colonias_permitidas(request.user),
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Cuenta para pagos guardada.")
        return redirect("tarifas_lista")
    return render(
        request,
        "core/formulario.html",
        {"form": form, "titulo": "Nueva cuenta para pagos", "volver": "tarifas_lista"},
    )
