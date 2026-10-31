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
    usuarios = User.objects.all().order_by("first_name", "last_name", "username")
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
    form = UsuarioForm(request.POST or None, colonias_queryset=colonias)
    if not request.user.es_superadmin:
        form.fields["rol"].choices = [
            choice for choice in User.Rol.choices if choice[0] in (User.Rol.GUARDIA, User.Rol.RESIDENTE)
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
    return render(request, "core/formulario.html", {"form": form, "titulo": "Nuevo usuario", "volver": "usuarios_lista"})


@roles_requeridos(*ROLES_GESTION)
def usuario_reset_password(request, pk):
    usuario = get_object_or_404(User, pk=pk, rol=User.Rol.RESIDENTE)
    if not request.user.es_superadmin:
        permitidas = colonias_permitidas(request.user)
        if not usuario.responsable.casas_actuales.filter(colonia__in=permitidas).exists():
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
