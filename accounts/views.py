from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from core.models import registrar_auditoria
from core.pagination import paginar

from .forms import CambioPasswordForm, LoginForm, UsuarioForm, generar_password_temporal
from .models import User
from .permissions import ROLES_GESTION, colonias_permitidas, roles_requeridos


class AccesoView(LoginView):
    authentication_form = LoginForm
    template_name = "registration/login.html"
    redirect_authenticated_user = True


@login_required
def cambiar_password_obligatorio(request):
    form = CambioPasswordForm(request.user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        user.debe_cambiar_password = False
        user.save(update_fields=("debe_cambiar_password",))
        update_session_auth_hash(request, user)
        registrar_auditoria(
            usuario=user,
            accion="CAMBIO_PASSWORD",
            objeto=user,
            descripcion="El usuario cambio su contraseña.",
        )
        messages.success(request, "Su contraseña fue actualizada correctamente.")
        return redirect("dashboard")
    return render(request, "accounts/cambiar_password.html", {"form": form})


@roles_requeridos(*ROLES_GESTION)
def usuarios_lista(request):
    usuarios = User.objects.all().prefetch_related("asignaciones_colonia__colonia").order_by(
        "first_name", "last_name", "username"
    )
    if not request.user.es_superadmin:
        permitidas = colonias_permitidas(request.user)
        usuarios = usuarios.filter(Q(asignaciones_colonia__colonia__in=permitidas) | Q(responsable__casas_actuales__colonia__in=permitidas)).distinct()
    buscar = request.GET.get("q", "").strip()
    if buscar:
        usuarios = usuarios.filter(
            Q(username__icontains=buscar)
            | Q(first_name__icontains=buscar)
            | Q(last_name__icontains=buscar)
            | Q(identidad__icontains=buscar)
        )
    page_obj = paginar(request, usuarios)
    return render(request, "accounts/usuarios_lista.html", {"usuarios": page_obj, "page_obj": page_obj, "buscar": buscar})


@roles_requeridos(*ROLES_GESTION)
def usuario_crear(request):
    colonias = colonias_permitidas(request.user).filter(activa=True)
    rol_solicitado = request.GET.get("rol", User.Rol.GUARDIA)
    roles_operativos = (User.Rol.GUARDIA, User.Rol.TESORERO)
    if rol_solicitado not in roles_operativos:
        rol_solicitado = User.Rol.GUARDIA
    form = UsuarioForm(
        request.POST or None,
        colonias_queryset=colonias,
        initial={"rol": rol_solicitado},
    )
    form.fields["rol"].choices = [
        choice for choice in User.Rol.choices if choice[0] in roles_operativos
    ]
    if request.method == "POST" and form.is_valid():
        usuario = form.save()
        registrar_auditoria(
            usuario=request.user,
            accion="CREACION_USUARIO",
            objeto=usuario,
            descripcion=f"Se creo el usuario {usuario.username} con rol {usuario.get_rol_display()}.",
            nuevos={"rol": usuario.rol, "identidad": usuario.identidad},
        )
        messages.success(request, "Usuario creado correctamente.")
        return redirect("usuarios_lista")
    return render(request, "accounts/usuario_form.html", {"form": form, "volver": "usuarios_lista"})


@roles_requeridos(*ROLES_GESTION)
def usuario_reset_password(request, pk):
    usuario = get_object_or_404(
        User,
        pk=pk,
        rol__in=(User.Rol.RESIDENTE, User.Rol.GUARDIA, User.Rol.TESORERO),
    )
    if not request.user.es_superadmin:
        permitidas = colonias_permitidas(request.user)
        asignado = usuario.asignaciones_colonia.filter(colonia__in=permitidas, activa=True).exists()
        from residentes.models import Responsable

        residente_asignado = Responsable.objects.filter(
            usuario=usuario,
            casas_actuales__colonia__in=permitidas,
        ).exists()
        if not asignado and not residente_asignado:
            raise PermissionDenied
    password = None
    if request.method == "POST":
        password = generar_password_temporal()
        usuario.set_password(password)
        usuario.debe_cambiar_password = True
        usuario.save(update_fields=("password", "debe_cambiar_password"))
        registrar_auditoria(
            usuario=request.user,
            accion="RESET_PASSWORD",
            objeto=usuario,
            descripcion="Se genero una contraseña temporal para el residente.",
        )
    return render(request, "accounts/reset_password.html", {"usuario_obj": usuario, "password_temporal": password})
