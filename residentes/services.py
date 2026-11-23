from datetime import timedelta
from uuid import uuid4

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from core.models import registrar_auditoria
from accounts.forms import generar_password_temporal
from accounts.models import User

from accounts.permissions import colonias_permitidas
from colonias.models import Casa, Colonia

from .models import CasaResponsable, Responsable


def crear_usuario_residente(responsable, password=None, *, username=None):
    if responsable.usuario_id:
        return responsable.usuario, None
    password = password or generar_password_temporal()
    partes = responsable.nombre_completo.strip().split()
    nombre = partes[0] if partes else ""
    apellido = " ".join(partes[1:])
    if username is None:
        username = responsable.identidad or f"residente-{responsable.pk}"
        if not responsable.identidad and User.objects.filter(username=username).exists():
            username = f"{username}-{uuid4().hex[:8]}"
    usuario = User.objects.create_user(
        username=username,
        identidad=responsable.identidad,
        email=responsable.correo,
        first_name=nombre[:150],
        last_name=apellido[:150],
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


@transaction.atomic
def registrar_residente(*, colonia, usuario, datos, vehiculo=None):
    if not colonias_permitidas(usuario).filter(pk=colonia.pk, activa=True).exists():
        raise PermissionDenied
    Colonia.objects.select_for_update().get(pk=colonia.pk)
    correo = (datos.get("correo") or "").strip()
    casa, _ = Casa.objects.get_or_create(
        colonia=colonia, codigo=datos["codigo_casa"],
        defaults={"numero": datos["codigo_casa"]},
    )
    casa = Casa.objects.select_for_update().get(pk=casa.pk)
    if not casa.activa or casa.responsable_actual_id:
        raise ValidationError("La casa ya tiene responsable o está inactiva.")
    responsable = Responsable(
        nombre_completo=datos["nombre_completo"], identidad=datos.get("identidad") or None,
        telefono=datos.get("telefono", ""), correo=correo, creado_por=usuario,
        banco=datos.get("banco", ""), numero_cuenta=datos.get("numero_cuenta", ""),
    )
    responsable.full_clean()
    responsable.save()
    _, temporal = crear_usuario_residente(responsable)
    asignar_responsable(casa=casa, responsable=responsable, usuario=usuario)
    if vehiculo is not None:
        vehiculo.casa = casa
        vehiculo.colonia = colonia
        vehiculo.responsable = responsable
        vehiculo.full_clean()
        vehiculo.save()
        registrar_auditoria(usuario=usuario, accion="CREAR", objeto=vehiculo,
                            descripcion="Vehículo registrado junto con el residente desde tesorería.")
    registrar_auditoria(usuario=usuario, accion="CREACION_RESPONSABLE", objeto=responsable,
                        descripcion="Residente registrado desde tesorería.")
    return casa, temporal
