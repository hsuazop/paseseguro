from datetime import date

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q
from django.db import transaction
from django.utils import timezone
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from accounts.models import User
from accounts.permissions import ROLES_GESTION, ROLES_FINANCIEROS, colonias_permitidas, roles_requeridos
from colonias.models import Casa
from core.models import registrar_auditoria
from core.pagination import paginar

from .forms import (
    AnularPagoForm,
    ComprobantePagoForm,
    CuentaPagoColoniaForm,
    GenerarCuotasForm,
    PagoForm,
    RevisarComprobanteForm,
    TarifaColoniaForm,
    TarifaEspecialForm,
)
from .models import ComprobanteCuota, ComprobantePago, CuentaPagoColonia, CuotaMensual, Pago, TarifaColonia, TarifaEspecialCasa
from .services import anular_pago, generar_cuotas_mes, registrar_pago


def _pagos_permitidos(user):
    if user.es_superadmin:
        return Pago.objects.all()
    if user.rol == User.Rol.RESIDENTE:
        try:
            return Pago.objects.filter(responsable=user.responsable)
        except Exception:
            return Pago.objects.none()
    return Pago.objects.filter(colonia__in=colonias_permitidas(user))


@roles_requeridos(*ROLES_GESTION)
def tarifas_lista(request):
    tarifas = TarifaColonia.objects.filter(colonia__in=colonias_permitidas(request.user)).select_related("colonia")
    especiales = TarifaEspecialCasa.objects.filter(casa__colonia__in=colonias_permitidas(request.user)).select_related("casa", "casa__colonia")
    return render(request, "facturacion/tarifas_lista.html", {"tarifas": tarifas, "especiales": especiales})


@roles_requeridos(*ROLES_GESTION)
def tarifa_crear(request):
    form = TarifaColoniaForm(request.POST or None, colonias_queryset=colonias_permitidas(request.user))
    if request.method == "POST" and form.is_valid():
        tarifa = form.save()
        registrar_auditoria(
            usuario=request.user, accion="CREACION_TARIFA", objeto=tarifa,
            descripcion=f"Tarifa base de L {tarifa.monto:.2f} creada.",
            nuevos={"monto": str(tarifa.monto), "fecha_inicio": str(tarifa.fecha_inicio)},
        )
        messages.success(request, "Tarifa creada correctamente.")
        return redirect("tarifas_lista")
    return render(request, "core/formulario.html", {"form": form, "titulo": "Nueva tarifa base", "volver": "tarifas_lista"})


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
    colonia_id = request.GET.get("colonia", "")
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
    form = ComprobantePagoForm(request.POST or None, request.FILES or None, initial={"fecha_pago": date.today()})
    if request.method == "POST" and form.is_valid():
        cuota_ids = request.POST.getlist("cuota_id")
        seleccionadas = list(cuotas.filter(pk__in=cuota_ids))
        if not seleccionadas:
            form.add_error(None, "Selecciona al menos una cuota a la que corresponde el comprobante.")
        else:
            with transaction.atomic():
                comprobante = form.save(commit=False)
                comprobante.casa = casa
                comprobante.colonia = casa.colonia
                comprobante.responsable = casa.responsable_actual
                comprobante.enviado_por = request.user
                comprobante.full_clean(exclude=("cuotas",))
                comprobante.save()
                ComprobanteCuota.objects.bulk_create(
                    [ComprobanteCuota(comprobante=comprobante, cuota=cuota) for cuota in seleccionadas]
                )
                registrar_auditoria(
                    usuario=request.user,
                    accion="ENVIO_COMPROBANTE",
                    objeto=comprobante,
                    descripcion=f"Comprobante por L {comprobante.monto:.2f} enviado.",
                )
            messages.success(request, "Comprobante enviado para revisión.")
            return redirect("comprobantes_residente", casa_id=casa.pk)
    return render(request, "facturacion/comprobante_enviar.html", {"casa": casa, "form": form, "cuotas": cuotas})


def cuenta_pago_residente(request, casa_id):
    casa = _casa_residente(request, casa_id)
    cuentas = CuentaPagoColonia.objects.filter(colonia=casa.colonia, activa=True)
    return render(request, "facturacion/cuentas_pago.html", {"casa": casa, "cuentas": cuentas})


@roles_requeridos(*ROLES_FINANCIEROS)
def comprobantes_gestion(request):
    comprobantes = ComprobantePago.objects.filter(colonia__in=colonias_permitidas(request.user)).select_related(
        "casa", "colonia", "responsable", "enviado_por", "revisado_por"
    ).prefetch_related("cuotas")
    estado = request.GET.get("estado")
    if estado:
        comprobantes = comprobantes.filter(estado=estado)
    page_obj = paginar(request, comprobantes)
    return render(
        request,
        "facturacion/comprobantes_gestion.html",
        {"comprobantes": page_obj, "page_obj": page_obj, "estados": ComprobantePago.Estado.choices},
    )


@roles_requeridos(*ROLES_FINANCIEROS)
def comprobante_revisar(request, pk):
    comprobante = get_object_or_404(
        ComprobantePago.objects.select_related("casa", "colonia", "responsable", "enviado_por").prefetch_related("cuotas"),
        pk=pk,
        colonia__in=colonias_permitidas(request.user),
    )
    form = RevisarComprobanteForm(
        request.POST or None,
        initial={"estado": comprobante.estado, "comentario_revision": comprobante.comentario_revision},
    )
    if request.method == "POST" and form.is_valid():
        anterior = comprobante.estado
        comprobante.estado = form.cleaned_data["estado"]
        comprobante.comentario_revision = form.cleaned_data["comentario_revision"]
        comprobante.revisado_por = request.user
        comprobante.revisado_en = timezone.now()
        comprobante.save(
            update_fields=("estado", "comentario_revision", "revisado_por", "revisado_en", "updated_at")
        )
        registrar_auditoria(
            usuario=request.user,
            accion="REVISION_COMPROBANTE",
            objeto=comprobante,
            descripcion=f"Comprobante cambiado de {anterior} a {comprobante.estado}.",
        )
        messages.success(request, "Comprobante revisado. Registra el pago para aplicar el dinero a las cuotas.")
        return redirect("comprobantes_gestion")
    return render(request, "facturacion/comprobante_revisar.html", {"comprobante": comprobante, "form": form})


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
