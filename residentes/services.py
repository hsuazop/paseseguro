from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from core.models import registrar_auditoria
from accounts.forms import generar_password_temporal
from accounts.models import User

from .models import CasaResponsable


def crear_usuario_residente(responsable, password=None):
    if responsable.usuario_id:
        return responsable.usuario, None
    password = password or generar_password_temporal()
    partes = responsable.nombre_completo.strip().split()
    nombre = partes[0] if partes else ""
    apellido = " ".join(partes[1:])
    usuario = User.objects.create_user(
        username=responsable.identidad,
        identidad=responsable.identidad,
        first_name=nombre,
        last_name=apellido,
        rol=User.Rol.RESIDENTE,
        password=password,
        debe_cambiar_password=True,
    )
    responsable.usuario = usuario
    responsable.save(update_fields=("usuario", "updated_at"))
    return usuario, password


@transaction.atomic
def asignar_responsable(*, casa, responsable, usuario, fecha_inicio=None):
    fecha_inicio = fecha_inicio or timezone.localdate()
    anterior = casa.responsable_actual
    activo = CasaResponsable.objects.select_for_update().filter(casa=casa, activo=True).first()
    if anterior == responsable and activo:
        return casa
    if anterior == responsable and not activo:
        CasaResponsable.objects.create(
            casa=casa, responsable=responsable, fecha_inicio=fecha_inicio, activo=True,
        )
        return casa
    if activo:
        if fecha_inicio < activo.fecha_inicio:
            raise ValidationError("La nueva fecha de inicio no puede ser anterior al historial vigente.")
        activo.activo = False
        activo.fecha_fin = fecha_inicio - timedelta(days=1)
        activo.save(update_fields=("activo", "fecha_fin", "updated_at"))

    CasaResponsable.objects.create(
        casa=casa,
        responsable=responsable,
        fecha_inicio=fecha_inicio,
        activo=True,
    )
    casa.responsable_actual = responsable
    casa.save(update_fields=("responsable_actual", "updated_at"))
    registrar_auditoria(
        usuario=usuario,
        accion="CAMBIO_RESPONSABLE",
        objeto=casa,
        descripcion=f"Responsable actual cambiado a {responsable.nombre_completo}.",
        anteriores={"responsable_id": anterior.pk if anterior else None},
        nuevos={"responsable_id": responsable.pk},
    )
    return casa
