from functools import wraps

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect

from .models import User


ROLES_GESTION = (User.Rol.ADMINISTRADOR,)
ROLES_FINANCIEROS = (User.Rol.ADMINISTRADOR, User.Rol.TESORERO)
ROLES_ACCESO = (User.Rol.ADMINISTRADOR, User.Rol.GUARDIA)


def colonias_permitidas(user):
    from colonias.models import Colonia

    if not user.is_authenticated:
        return Colonia.objects.none()
    if user.es_superadmin:
        return Colonia.objects.all()
    if user.rol == User.Rol.RESIDENTE:
        colonias = Colonia.objects.filter(
            casas__responsable_actual__usuario=user, casas__activa=True, activa=True,
        ).distinct()
    else:
        colonias = Colonia.objects.filter(usuarios_asignados__usuario=user, usuarios_asignados__activa=True).distinct()
    if not puede_elegir_colonia(user):
        colonias = colonias.filter(activa=True)
        return colonias.filter(pk__in=colonias.order_by("pk").values("pk")[:1])
    return colonias


def puede_elegir_colonia(user):
    return user.is_authenticated and (user.es_superadmin or user.rol == User.Rol.ADMINISTRADOR)


def filtro_colonia(request):
    """Los filtros enviados por un perfil operativo nunca cambian su residencial."""
    if puede_elegir_colonia(request.user):
        return request.GET.get("colonia", "")
    return str(colonias_permitidas(request.user).values_list("pk", flat=True).first() or "")


def colonia_actual(request):
    colonias = colonias_permitidas(request.user).filter(activa=True)
    if puede_elegir_colonia(request.user):
        colonia_id = request.GET.get("colonia") or request.POST.get("colonia") or request.session.get("colonia_actual")
        try:
            colonia = colonias.filter(pk=colonia_id).first() if colonia_id else colonias.first()
        except (TypeError, ValueError):
            colonia = None
    else:
        colonia = colonias.first()
    if colonia:
        request.session["colonia_actual"] = colonia.pk
    return colonias, colonia


def fijar_colonia_formulario(form, user):
    """Asigna la colonia en el servidor y elimina el campo del formulario."""
    if not puede_elegir_colonia(user):
        colonia = colonias_permitidas(user).first()
        if not colonia:
            raise PermissionDenied("No tiene una residencial activa asignada.")
        form.fields.pop("colonia", None)
        form.instance.colonia = colonia
    return form


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
