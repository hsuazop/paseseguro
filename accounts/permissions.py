from functools import wraps

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect

from .models import User


ROLES_GESTION = (User.Rol.ADMINISTRADOR,)
ROLES_FINANCIEROS = (User.Rol.ADMINISTRADOR,)
ROLES_ACCESO = (User.Rol.ADMINISTRADOR, User.Rol.GUARDIA)


def colonias_permitidas(user):
    from colonias.models import Colonia

    if not user.is_authenticated:
        return Colonia.objects.none()
    if user.es_superadmin:
        return Colonia.objects.all()
    return Colonia.objects.filter(usuarios_asignados__usuario=user, usuarios_asignados__activa=True).distinct()


def puede_acceder_colonia(user, colonia_id):
    return colonias_permitidas(user).filter(pk=colonia_id).exists()


def roles_requeridos(*roles):
    def decorator(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect("login")
            if not (request.user.es_superadmin or request.user.rol in roles):
                raise PermissionDenied("No tiene permiso para realizar esta accion.")
            return view(request, *args, **kwargs)

        return wrapped

    return decorator


class RoleRequiredMixin(LoginRequiredMixin):
    allowed_roles = ()

    def dispatch(self, request, *args, **kwargs):
        if not (request.user.es_superadmin or request.user.rol in self.allowed_roles):
            raise PermissionDenied("No tiene permiso para acceder a esta pagina.")
        return super().dispatch(request, *args, **kwargs)


def exigir_cambio_password(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if request.user.is_authenticated and request.user.debe_cambiar_password:
            messages.warning(request, "Debe cambiar su contraseña temporal antes de continuar.")
            return redirect("cambiar_password_obligatorio")
        return view(request, *args, **kwargs)

    return wrapped
