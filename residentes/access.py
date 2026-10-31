from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404

from .models import Responsable


def responsable_del_usuario(user):
    try:
        return user.responsable
    except Responsable.DoesNotExist:
        raise PermissionDenied("Su usuario no está vinculado a un responsable.")


def casa_del_residente(user, casa_id):
    responsable = responsable_del_usuario(user)
    return get_object_or_404(
        responsable.casas_actuales.filter(activa=True).select_related("colonia", "responsable_actual"),
        pk=casa_id,
    )

