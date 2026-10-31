from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from accounts.models import User
from accounts.permissions import ROLES_ACCESO, colonias_permitidas, roles_requeridos
from residentes.access import casa_del_residente

from .forms import VisitaForm
from .models import Visita
from .tokens import crear_token_residente, leer_token_residente


def _exigir_residente(user):
    if user.rol != User.Rol.RESIDENTE and not user.es_superadmin:
        raise PermissionDenied


@login_required
def visitas_lista(request, casa_id):
    _exigir_residente(request.user)
    casa = casa_del_residente(request.user, casa_id)
    visitas = casa.visitas.filter(creado_por=request.user)
    return render(request, "visitas/lista.html", {"casa": casa, "visitas": visitas})


@login_required
def visita_crear(request, casa_id):
    _exigir_residente(request.user)
    casa = casa_del_residente(request.user, casa_id)
    form = VisitaForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        visita = form.save(commit=False)
        visita.casa = casa
        visita.creado_por = request.user
        visita.full_clean()
        visita.save()
        messages.success(request, "Visita registrada. Ya puedes compartir su acceso.")
        return redirect("visita_detalle", casa_id=casa.pk, pk=visita.pk)
    return render(request, "visitas/formulario.html", {"casa": casa, "form": form})


@login_required
def visita_detalle(request, casa_id, pk):
    _exigir_residente(request.user)
    casa = casa_del_residente(request.user, casa_id)
    visita = get_object_or_404(Visita, pk=pk, casa=casa, creado_por=request.user)
    acceso_url = request.build_absolute_uri(reverse("visita_publica", kwargs={"token": visita.token_publico}))
    return render(request, "visitas/detalle.html", {"casa": casa, "visita": visita, "acceso_url": acceso_url})


@login_required
def visita_cancelar(request, casa_id, pk):
    _exigir_residente(request.user)
    casa = casa_del_residente(request.user, casa_id)
    visita = get_object_or_404(Visita, pk=pk, casa=casa, creado_por=request.user)
    if request.method == "POST":
        visita.activa = False
        visita.save(update_fields=("activa", "updated_at"))
        messages.success(request, "La visita fue cancelada.")
    return redirect("visitas_lista", casa_id=casa.pk)


@login_required
def qr_residente(request, casa_id):
    _exigir_residente(request.user)
    casa = casa_del_residente(request.user, casa_id)
    return render(request, "visitas/qr_residente.html", {"casa": casa})


@login_required
def token_qr_residente(request, casa_id):
    _exigir_residente(request.user)
    casa = casa_del_residente(request.user, casa_id)
    token = crear_token_residente(usuario_id=request.user.pk, casa_id=casa.pk)
    url = request.build_absolute_uri(reverse("verificar_qr_residente", kwargs={"token": token}))
    return JsonResponse({"token": token, "url": url, "vigencia_segundos": 30})


def verificar_qr_residente(request, token):
    try:
        payload = leer_token_residente(token)
    except Exception:
        return render(request, "visitas/verificacion.html", {"valido": False}, status=400)

    from colonias.models import Casa

    casa = Casa.objects.filter(pk=payload.get("c"), activa=True).select_related("colonia", "responsable_actual").first()
    valido = bool(casa and casa.responsable_actual and casa.responsable_actual.usuario_id == payload.get("u"))
    return render(request, "visitas/verificacion.html", {"valido": valido, "casa": casa})


def visita_publica(request, token):
    visita = get_object_or_404(Visita.objects.select_related("casa", "casa__colonia"), token_publico=token)
    return render(request, "visitas/publica.html", {"visita": visita})


@roles_requeridos(*ROLES_ACCESO)
def visitas_control(request):
    visitas = Visita.objects.filter(casa__colonia__in=colonias_permitidas(request.user)).select_related(
        "casa", "casa__colonia", "creado_por"
    )[:200]
    return render(request, "visitas/control.html", {"visitas": visitas})


@roles_requeridos(*ROLES_ACCESO)
def visita_registrar_acceso(request, pk):
    visita = get_object_or_404(
        Visita.objects.select_related("casa", "casa__colonia"),
        pk=pk,
        casa__colonia__in=colonias_permitidas(request.user),
    )
    if request.method == "POST":
        if not visita.vigente:
            messages.error(request, "Este acceso no está vigente o ya agotó sus usos.")
        else:
            from .models import RegistroAcceso

            RegistroAcceso.objects.create(visita=visita, registrado_por=request.user, personas=1)
            visita.usos_actuales += 1
            visita.save(update_fields=("usos_actuales", "updated_at"))
            messages.success(request, "Entrada registrada correctamente.")
    return redirect("visitas_control")

