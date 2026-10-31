from datetime import date
from decimal import Decimal

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required

from accounts.models import User
from accounts.permissions import ROLES_GESTION, colonias_permitidas, roles_requeridos
from facturacion.models import AplicacionPago, CuotaMensual
from facturacion.services import obtener_saldo_casa
from core.pagination import paginar

from .access import casa_del_residente, responsable_del_usuario
from .forms import PerfilResidenteForm, ResponsableForm
from .models import Responsable
from .services import crear_usuario_residente


def _responsables_permitidos(user):
    if user.es_superadmin:
        return Responsable.objects.all()
    return Responsable.objects.filter(
        Q(casas_actuales__colonia__in=colonias_permitidas(user)) | Q(creado_por=user)
    ).distinct()


@roles_requeridos(*ROLES_GESTION)
def responsables_lista(request):
    responsables = _responsables_permitidos(request.user).select_related("usuario")
    buscar = request.GET.get("q", "").strip()
    if buscar:
        responsables = responsables.filter(
            Q(nombre_completo__icontains=buscar) | Q(identidad__icontains=buscar) | Q(telefono__icontains=buscar)
        )
    page_obj = paginar(request, responsables)
    return render(request, "residentes/responsables_lista.html", {"responsables": page_obj, "page_obj": page_obj, "buscar": buscar})


@roles_requeridos(*ROLES_GESTION)
def responsable_crear(request):
    form = ResponsableForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        responsable = form.save(commit=False)
        responsable.creado_por = request.user
        responsable.save()
        temporal = None
        if form.cleaned_data["crear_usuario"]:
            _, temporal = crear_usuario_residente(responsable)
        return render(request, "residentes/responsable_creado.html", {
            "responsable": responsable, "password_temporal": temporal,
        })
    return render(request, "core/formulario.html", {"form": form, "titulo": "Nuevo responsable", "volver": "responsables_lista"})


@roles_requeridos(*ROLES_GESTION)
def responsable_detalle(request, pk):
    responsable = get_object_or_404(_responsables_permitidos(request.user).select_related("usuario"), pk=pk)
    casas = responsable.casas_actuales.filter(colonia__in=colonias_permitidas(request.user)).select_related("colonia")
    return render(request, "residentes/responsable_detalle.html", {"responsable": responsable, "casas": casas})


def _responsable_actual(user):
    return responsable_del_usuario(user)


def _casa_residente(user, pk):
    return casa_del_residente(user, pk)


def mi_cuenta(request):
    if not request.user.is_authenticated:
        return redirect("login")
    if request.user.rol != User.Rol.RESIDENTE and not request.user.es_superadmin:
        raise PermissionDenied
    responsable = _responsable_actual(request.user)
    casas = responsable.casas_actuales.filter(activa=True).select_related("colonia")
    resumen = [{"casa": casa, "saldo": obtener_saldo_casa(casa)} for casa in casas]
    if len(resumen) == 1:
        return redirect("portal_residente", casa_id=resumen[0]["casa"].pk)
    return render(request, "residentes/mi_cuenta.html", {"responsable": responsable, "propiedades": resumen})


def mi_cuenta_casa(request, casa_id):
    if not request.user.is_authenticated:
        return redirect("login")
    casa = _casa_residente(request.user, casa_id)
    responsable = _responsable_actual(request.user)
    anio = int(request.GET.get("anio", date.today().year))
    cuotas_qs = responsable.cuotas.filter(colonia=casa.colonia, anio=anio).exclude(
        estado=CuotaMensual.Estado.ANULADA
    )
    cuotas_map = {c.mes: c for c in cuotas_qs}
    cuotas = [{"numero": numero, "nombre": nombre, "cuota": cuotas_map.get(numero)} for numero, nombre in CuotaMensual.MESES]
    saldo_total = obtener_saldo_casa(casa)
    pagado_anio = AplicacionPago.objects.filter(
        cuota_mensual__responsable=responsable,
        cuota_mensual__colonia=casa.colonia,
        cuota_mensual__anio=anio,
        pago__anulado=False,
    ).aggregate(total=Sum("monto_aplicado"))["total"] or Decimal("0")
    anios = list(
        responsable.cuotas.filter(colonia=casa.colonia).values_list("anio", flat=True).distinct().order_by("-anio")
    )
    if anio not in anios:
        anios.append(anio)
    pagos = responsable.pagos.filter(colonia=casa.colonia, anulado=False).prefetch_related("aplicaciones")[:20]
    return render(request, "residentes/estado_cuenta.html", {
        "casa": casa, "cuotas": cuotas, "anio": anio, "anios": sorted(anios, reverse=True),
        "saldo_total": saldo_total, "pagado_anio": pagado_anio, "pagos": pagos,
    })


@login_required
def portal_residente(request, casa_id):
    if request.user.rol != User.Rol.RESIDENTE and not request.user.es_superadmin:
        raise PermissionDenied
    casa = _casa_residente(request.user, casa_id)
    responsable = _responsable_actual(request.user)
    hoy = date.today()
    cuotas_anio = responsable.cuotas.filter(colonia=casa.colonia, anio=hoy.year).exclude(
        estado=CuotaMensual.Estado.ANULADA
    )
    pagado_anio = AplicacionPago.objects.filter(
        cuota_mensual__in=cuotas_anio,
        pago__anulado=False,
    ).aggregate(total=Sum("monto_aplicado"))["total"] or Decimal("0")

    from comunidad.models import Comunicado, SolicitudMensaje
    from facturacion.models import ComprobantePago
    from reservas.models import Reserva
    from visitas.models import Visita

    contexto = {
        "casa": casa,
        "responsable": responsable,
        "saldo_total": obtener_saldo_casa(casa),
        "pagado_anio": pagado_anio,
        "visitas_activas": Visita.objects.filter(casa=casa, activa=True, fecha_inicio__date__gte=hoy).count(),
        "solicitudes_pendientes": SolicitudMensaje.objects.filter(casa=casa).exclude(
            estado=SolicitudMensaje.Estado.RESUELTO
        ).count(),
        "comprobantes_pendientes": ComprobantePago.objects.filter(
            casa=casa, estado=ComprobantePago.Estado.PENDIENTE
        ).count(),
        "reservas_pendientes": Reserva.objects.filter(casa=casa, estado=Reserva.Estado.PENDIENTE).count(),
        "comunicados": Comunicado.objects.filter(colonia=casa.colonia, activo=True)[:3],
    }
    return render(request, "portal/inicio.html", contexto)


@login_required
def configurar_perfil(request, casa_id):
    if request.user.rol != User.Rol.RESIDENTE and not request.user.es_superadmin:
        raise PermissionDenied
    casa = _casa_residente(request.user, casa_id)
    responsable = _responsable_actual(request.user)
    form = PerfilResidenteForm(
        request.POST or None,
        usuario=request.user,
        responsable=responsable,
    )
    if request.method == "POST" and form.is_valid():
        request.user.first_name = form.cleaned_data["nombre"]
        request.user.last_name = form.cleaned_data["apellido"]
        request.user.email = form.cleaned_data["correo"]
        responsable.telefono = form.cleaned_data["telefono"]
        responsable.nombre_completo = request.user.get_full_name() or responsable.nombre_completo
        nueva = form.cleaned_data.get("password_nueva")
        if nueva:
            request.user.set_password(nueva)
        request.user.save()
        responsable.save(update_fields=("telefono", "nombre_completo", "updated_at"))
        if nueva:
            update_session_auth_hash(request, request.user)
        messages.success(request, "Tu información fue actualizada.")
        return redirect("configurar_perfil", casa_id=casa.pk)
    return render(request, "portal/configuracion.html", {"casa": casa, "form": form})
