from django import forms
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Prefetch, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.crypto import constant_time_compare, salted_hmac
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_safe

from accounts.forms import generar_password_temporal
from accounts.models import User
from accounts.permissions import ROLES_FINANCIEROS, colonia_actual, roles_requeridos
from colonias.models import Casa
from core.models import registrar_auditoria
from core.pagination import paginar
from .models import RegistroPublico, Responsable
from .services import crear_usuario_residente, enviar_credenciales_residente


class CorreoResidenteForm(forms.Form):
    correo = forms.EmailField(
        label="Correo electrónico", required=False, max_length=254,
        widget=forms.EmailInput(attrs={"class": "form-control"}),
    )


def _residentes(colonia, buscar=""):
    if not colonia:
        return Responsable.objects.none()
    casas = Casa.objects.filter(colonia=colonia, responsable_actual__isnull=False)
    pendientes = RegistroPublico.objects.filter(colonia=colonia, confirmado=False)
    residentes = Responsable.objects.filter(
        Q(pk__in=casas.values("responsable_actual_id")) | Q(pk__in=pendientes.values("responsable_id"))
    )
    if buscar:
        residentes = residentes.filter(
            Q(nombre_completo__icontains=buscar) | Q(identidad__icontains=buscar) |
            Q(telefono__icontains=buscar) | Q(correo__icontains=buscar) |
            Q(pk__in=casas.filter(codigo__icontains=buscar).values("responsable_actual_id")) |
            Q(pk__in=pendientes.filter(descripcion_casa__icontains=buscar).values("responsable_id"))
        )
    return residentes


@roles_requeridos(*ROLES_FINANCIEROS)
@never_cache
@require_safe
def lista(request):
    _, colonia = colonia_actual(request)
    buscar = request.GET.get("q", "").strip()
    residentes = _residentes(colonia, buscar).select_related("registropublico").prefetch_related(
        Prefetch("casas_actuales", queryset=Casa.objects.filter(colonia=colonia).order_by("codigo"), to_attr="casas_locales"),
    ).order_by("nombre_completo", "pk")
    return render(request, "residentes/tesoreria_lista.html", {
        "colonia": colonia, "buscar": buscar, "page_obj": paginar(request, residentes),
    })


def _puede_editar(residente, usuario, colonia):
    if not residente.activo or residente.casas_actuales.exclude(colonia=colonia).exists():
        return False
    if RegistroPublico.objects.filter(responsable=residente, confirmado=False).exclude(colonia=colonia).exists():
        return False
    return usuario is None or (
        usuario.rol == User.Rol.RESIDENTE and usuario.is_active and not usuario.is_staff and not usuario.is_superuser
        and not usuario.groups.exists() and not usuario.user_permissions.exists()
        and not usuario.asignaciones_colonia.filter(activa=True).exclude(colonia=colonia).exists()
    )


def _version(residente, usuario):
    estado = (residente.pk, residente.correo, usuario and usuario.pk, usuario and usuario.username,
              usuario and usuario.email, usuario and usuario.password)
    return salted_hmac("tesoreria.residente", repr(estado)).hexdigest()


@transaction.atomic
def _guardar(request, pk, colonia, accion, correo):
    residente = get_object_or_404(_residentes(colonia).select_for_update(), pk=pk)
    usuario = User.objects.select_for_update().get(pk=residente.usuario_id) if residente.usuario_id else None
    if not _puede_editar(residente, usuario, colonia):
        raise PermissionDenied
    if not constant_time_compare(request.POST.get("version", ""), _version(residente, usuario)):
        raise ValidationError("Los datos de acceso cambiaron. Revise los datos actuales antes de continuar.")
    if accion == "correo":
        correo = correo.lower()
        usa_correo = usuario and "@" in usuario.username
        if usa_correo and (not correo or len(correo) > User._meta.get_field("username").max_length):
            raise ValidationError("Este residente ingresa con su correo. Indique una dirección de hasta 150 caracteres.")
        if correo and User.objects.exclude(pk=residente.usuario_id).filter(
            Q(email__iexact=correo) | Q(username__iexact=correo)
        ).exists():
            raise ValidationError("Este correo ya está en uso.")
        if usuario:
            usuario.email = correo
            if usa_correo:
                usuario.username = correo
            usuario.save(update_fields=["email", "username"])
        residente.correo = correo
        residente.save(update_fields=["correo", "updated_at"])
        registrar_auditoria(usuario=request.user, accion="CAMBIO_CORREO_RESIDENTE", objeto=residente,
                            descripcion="Tesorería actualizó el correo del residente.")
        return usuario, None
    if usuario is None:
        usuario, clave = crear_usuario_residente(residente)
    else:
        clave = generar_password_temporal()
        usuario.set_password(clave)
        usuario.debe_cambiar_password = True
        usuario.save(update_fields=["password", "debe_cambiar_password"])
    registrar_auditoria(usuario=request.user, accion="RESET_PASSWORD", objeto=usuario,
                        descripcion="Tesorería generó una contraseña temporal para el residente.")
    return usuario, clave


@roles_requeridos(*ROLES_FINANCIEROS)
@never_cache
@require_http_methods(["GET", "POST"])
def acceso(request, pk):
    _, colonia = colonia_actual(request)
    residente = get_object_or_404(_residentes(colonia).select_related("usuario"), pk=pk)
    accion = request.POST.get("accion")
    form = CorreoResidenteForm(request.POST if accion == "correo" else None, initial={"correo": residente.correo})
    sesion = f"acceso_residente_{colonia.pk}_{pk}"
    if request.method == "POST":
        if accion not in ("correo", "clave"):
            raise Http404
        if accion == "clave" or form.is_valid():
            try:
                usuario, clave = _guardar(request, pk, colonia, accion, form.cleaned_data["correo"] if accion == "correo" else None)
            except (ValidationError, IntegrityError) as exc:
                messages.error(request, " ".join(exc.messages) if isinstance(exc, ValidationError) else "Los datos entran en conflicto con otra cuenta.")
                return redirect("tesoreria_residente_acceso", pk=pk)
            if clave:
                enviado = bool(usuario.email) and enviar_credenciales_residente(
                    usuario, clave, colonia, request.build_absolute_uri(reverse("login")), restablecida=True,
                )
                request.session[sesion] = {"usuario": usuario.username, "clave": clave, "correo": usuario.email, "enviado": enviado}
            else:
                messages.success(request, "Correo actualizado.")
            return redirect("tesoreria_residente_acceso", pk=pk)
    editable = _puede_editar(residente, residente.usuario, colonia)
    resultado = request.session.pop(sesion, None) if request.method == "GET" else None
    return render(request, "residentes/tesoreria_acceso.html", {
        "residente": residente, "colonia": colonia, "form": form, "editable": editable,
        "version": _version(residente, residente.usuario) if editable else "",
        "resultado": resultado if editable else None,
    })
