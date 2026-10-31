from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.models import User
from accounts.permissions import ROLES_FINANCIEROS, colonias_permitidas, roles_requeridos
from residentes.access import casa_del_residente

from .forms import (
    AlertaSOSForm,
    ClasificadoForm,
    ComunicadoForm,
    DirectorioEntradaForm,
    DocumentoComunidadForm,
    ResponderSolicitudForm,
    SolicitudMensajeForm,
)
from .models import AlertaSOS, Clasificado, Comunicado, DirectorioEntrada, DocumentoComunidad, SolicitudMensaje


def _exigir_residente(user):
    if user.rol != User.Rol.RESIDENTE and not user.es_superadmin:
        raise PermissionDenied


@login_required
def solicitudes_lista(request, casa_id):
    _exigir_residente(request.user)
    casa = casa_del_residente(request.user, casa_id)
    solicitudes = SolicitudMensaje.objects.filter(casa=casa, usuario=request.user)
    return render(request, "comunidad/solicitudes_lista.html", {"casa": casa, "solicitudes": solicitudes})


@login_required
def solicitud_crear(request, casa_id):
    _exigir_residente(request.user)
    casa = casa_del_residente(request.user, casa_id)
    form = SolicitudMensajeForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        solicitud = form.save(commit=False)
        solicitud.casa = casa
        solicitud.colonia = casa.colonia
        solicitud.usuario = request.user
        solicitud.save()
        messages.success(request, "Tu mensaje fue enviado a la administración.")
        return redirect("solicitudes_lista", casa_id=casa.pk)
    return render(request, "comunidad/solicitud_form.html", {"casa": casa, "form": form})


@login_required
def comunidad_muro(request, casa_id):
    _exigir_residente(request.user)
    casa = casa_del_residente(request.user, casa_id)
    publicaciones = SolicitudMensaje.objects.filter(
        colonia=casa.colonia,
        visibilidad=SolicitudMensaje.Visibilidad.PUBLICA,
    ).select_related("usuario", "casa")[:100]
    return render(request, "comunidad/muro.html", {"casa": casa, "publicaciones": publicaciones})


@login_required
def alerta_sos(request, casa_id):
    _exigir_residente(request.user)
    casa = casa_del_residente(request.user, casa_id)
    form = AlertaSOSForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        alerta = form.save(commit=False)
        alerta.casa = casa
        alerta.colonia = casa.colonia
        alerta.usuario = request.user
        alerta.save()
        messages.success(request, "Alerta enviada. El personal autorizado ya puede verla.")
        return redirect("portal_residente", casa_id=casa.pk)
    return render(request, "comunidad/sos.html", {"casa": casa, "form": form})


@login_required
def comunicados_lista(request, casa_id):
    _exigir_residente(request.user)
    casa = casa_del_residente(request.user, casa_id)
    comunicados = Comunicado.objects.filter(colonia=casa.colonia, activo=True)
    return render(request, "comunidad/comunicados.html", {"casa": casa, "comunicados": comunicados})


@login_required
def clasificados_lista(request, casa_id):
    _exigir_residente(request.user)
    casa = casa_del_residente(request.user, casa_id)
    clasificados = Clasificado.objects.filter(colonia=casa.colonia, activo=True).select_related("usuario")
    return render(request, "comunidad/clasificados.html", {"casa": casa, "clasificados": clasificados})


@login_required
def clasificado_crear(request, casa_id):
    _exigir_residente(request.user)
    casa = casa_del_residente(request.user, casa_id)
    form = ClasificadoForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        clasificado = form.save(commit=False)
        clasificado.colonia = casa.colonia
        clasificado.usuario = request.user
        clasificado.save()
        messages.success(request, "Clasificado publicado.")
        return redirect("clasificados_lista", casa_id=casa.pk)
    return render(request, "comunidad/clasificado_form.html", {"casa": casa, "form": form})


@login_required
def directorio_documentos(request, casa_id):
    _exigir_residente(request.user)
    casa = casa_del_residente(request.user, casa_id)
    directorio = DirectorioEntrada.objects.filter(colonia=casa.colonia, activo=True)
    documentos = DocumentoComunidad.objects.filter(colonia=casa.colonia, activo=True)
    return render(
        request,
        "comunidad/directorio.html",
        {"casa": casa, "directorio": directorio, "documentos": documentos},
    )


@roles_requeridos(*ROLES_FINANCIEROS)
def bandeja_comunidad(request):
    colonias = colonias_permitidas(request.user)
    solicitudes = SolicitudMensaje.objects.filter(colonia__in=colonias).select_related("casa", "usuario", "colonia")[:200]
    alertas = AlertaSOS.objects.filter(colonia__in=colonias).select_related("casa", "usuario", "colonia")[:100]
    return render(request, "comunidad/bandeja.html", {"solicitudes": solicitudes, "alertas": alertas})


@roles_requeridos(*ROLES_FINANCIEROS)
def solicitud_responder(request, pk):
    solicitud = get_object_or_404(
        SolicitudMensaje.objects.select_related("casa", "colonia", "usuario"),
        pk=pk,
        colonia__in=colonias_permitidas(request.user),
    )
    form = ResponderSolicitudForm(
        request.POST or None,
        initial={"estado": solicitud.estado, "respuesta": solicitud.respuesta},
    )
    if request.method == "POST" and form.is_valid():
        solicitud.estado = form.cleaned_data["estado"]
        solicitud.respuesta = form.cleaned_data["respuesta"]
        solicitud.respondido_por = request.user
        solicitud.respondido_en = timezone.now()
        solicitud.save(update_fields=("estado", "respuesta", "respondido_por", "respondido_en", "updated_at"))
        messages.success(request, "Respuesta guardada.")
        return redirect("bandeja_comunidad")
    return render(request, "comunidad/responder.html", {"solicitud": solicitud, "form": form})


def _crear_catalogo(request, form_class, titulo, volver="bandeja_comunidad"):
    form = form_class(request.POST or None, request.FILES or None, colonias_queryset=colonias_permitidas(request.user))
    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)
        if hasattr(obj, "publicado_por_id"):
            obj.publicado_por = request.user
        obj.save()
        messages.success(request, f"{titulo} guardado correctamente.")
        return redirect(volver)
    return render(request, "comunidad/catalogo_form.html", {"form": form, "titulo": titulo})


@roles_requeridos(*ROLES_FINANCIEROS)
def comunicado_crear(request):
    return _crear_catalogo(request, ComunicadoForm, "Comunicado")


@roles_requeridos(*ROLES_FINANCIEROS)
def directorio_crear(request):
    return _crear_catalogo(request, DirectorioEntradaForm, "Contacto del directorio")


@roles_requeridos(*ROLES_FINANCIEROS)
def documento_crear(request):
    return _crear_catalogo(request, DocumentoComunidadForm, "Documento")

