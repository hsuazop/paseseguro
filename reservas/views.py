from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render

from accounts.models import User
from accounts.permissions import ROLES_FINANCIEROS, colonias_permitidas, roles_requeridos
from residentes.access import casa_del_residente

from .forms import AreaComunForm, ReservaForm, RevisarReservaForm
from .models import AreaComun, Reserva


def _exigir_residente(user):
    if user.rol != User.Rol.RESIDENTE and not user.es_superadmin:
        raise PermissionDenied


@login_required
def areas_lista(request, casa_id):
    _exigir_residente(request.user)
    casa = casa_del_residente(request.user, casa_id)
    areas = AreaComun.objects.filter(colonia=casa.colonia, activa=True)
    propias = Reserva.objects.filter(casa=casa, usuario=request.user).select_related("area")[:20]
    return render(request, "reservas/areas.html", {"casa": casa, "areas": areas, "reservas": propias})


@login_required
def reserva_crear(request, casa_id, area_id=None):
    _exigir_residente(request.user)
    casa = casa_del_residente(request.user, casa_id)
    areas = AreaComun.objects.filter(colonia=casa.colonia, activa=True)
    area = get_object_or_404(areas, pk=area_id) if area_id else None
    form = ReservaForm(request.POST or None, areas_queryset=areas, initial={"area": area})
    if request.method == "POST" and form.is_valid():
        reserva = form.save(commit=False)
        reserva.casa = casa
        reserva.usuario = request.user
        reserva.estado = Reserva.Estado.PENDIENTE if reserva.area.requiere_aprobacion else Reserva.Estado.APROBADA
        reserva.full_clean()
        reserva.save()
        messages.success(request, "Reservación enviada correctamente.")
        return redirect("areas_lista", casa_id=casa.pk)
    return render(request, "reservas/formulario.html", {"casa": casa, "area": area, "form": form})


@login_required
def reserva_cancelar(request, casa_id, pk):
    _exigir_residente(request.user)
    casa = casa_del_residente(request.user, casa_id)
    reserva = get_object_or_404(Reserva, pk=pk, casa=casa, usuario=request.user)
    if request.method == "POST" and reserva.estado in (Reserva.Estado.PENDIENTE, Reserva.Estado.APROBADA):
        reserva.estado = Reserva.Estado.CANCELADA
        reserva.save(update_fields=("estado", "updated_at"))
        messages.success(request, "Reservación cancelada.")
    return redirect("areas_lista", casa_id=casa.pk)


@roles_requeridos(*ROLES_FINANCIEROS)
def reservas_gestion(request):
    reservas = Reserva.objects.filter(area__colonia__in=colonias_permitidas(request.user)).select_related(
        "area", "casa", "casa__colonia", "usuario"
    )[:200]
    return render(request, "reservas/gestion.html", {"reservas": reservas})


@roles_requeridos(*ROLES_FINANCIEROS)
def reserva_revisar(request, pk):
    reserva = get_object_or_404(
        Reserva.objects.select_related("area", "casa", "casa__colonia", "usuario"),
        pk=pk,
        area__colonia__in=colonias_permitidas(request.user),
    )
    form = RevisarReservaForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        reserva.estado = form.cleaned_data["estado"]
        reserva.observacion_revision = form.cleaned_data["observacion"]
        reserva.revisado_por = request.user
        reserva.save(update_fields=("estado", "observacion_revision", "revisado_por", "updated_at"))
        messages.success(request, "Reservación revisada.")
        return redirect("reservas_gestion")
    return render(request, "reservas/revisar.html", {"reserva": reserva, "form": form})


@roles_requeridos(*ROLES_FINANCIEROS)
def area_crear(request):
    form = AreaComunForm(
        request.POST or None,
        request.FILES or None,
        colonias_queryset=colonias_permitidas(request.user),
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Área común creada.")
        return redirect("reservas_gestion")
    return render(request, "reservas/area_form.html", {"form": form})

