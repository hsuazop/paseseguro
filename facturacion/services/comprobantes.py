from decimal import Decimal
from datetime import timedelta
from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.mail import send_mail
from django.core.validators import validate_email
from django.db import transaction
from django.utils import timezone
from core.models import registrar_auditoria
from accounts.permissions import colonias_permitidas
from colonias.models import Casa, Colonia
from facturacion.models import ComprobantePago, ComprobanteCuota, CuotaMensual
from .cuotas import asegurar_cuota
from .pagos import registrar_pago


def registrar_comprobante_tesoreria(*, colonia, usuario, datos):
    item = None
    try:
        with transaction.atomic():
            if not colonias_permitidas(usuario).filter(pk=colonia.pk, activa=True).exists():
                raise PermissionDenied
            Colonia.objects.select_for_update().get(pk=colonia.pk)
            anterior = ComprobantePago.objects.filter(registro_tesoreria=datos["operacion"]).first()
            if anterior:
                if anterior.colonia_id != colonia.pk or anterior.enviado_por_id != usuario.pk:
                    raise PermissionDenied
                return anterior.pago
            casa = Casa.objects.select_for_update().filter(pk=datos["casa"].pk, colonia=colonia, activa=True).first()
            if not casa or not casa.responsable_actual or not casa.responsable_actual.activo:
                raise ValidationError("Seleccione una casa con residente activo.")
            cuota = asegurar_cuota(casa=casa, anio=datos["anio"], mes=datos["mes"], usuario=usuario)
            pago = registrar_pago(
                casa=casa, responsable=casa.responsable_actual, fecha_pago=datos["fecha_pago"],
                monto_total=datos["monto_total"], metodo_pago=datos["metodo_pago"], usuario=usuario,
                referencia=datos.get("referencia", ""),
                observaciones=datos["observaciones"], aplicaciones=[{"cuota_id": cuota.pk, "monto": datos["monto_total"]}],
            )
            item = ComprobantePago(
                casa=casa, colonia=colonia, responsable=casa.responsable_actual, enviado_por=usuario,
                revisado_por=usuario, revisado_en=timezone.now(), estado=ComprobantePago.Estado.APROBADO,
                pago=pago, registro_tesoreria=datos["operacion"], fecha_pago=pago.fecha_pago, monto=pago.monto_total,
                metodo_pago=pago.metodo_pago, banco=datos["banco"], numero_cuenta=datos["numero_cuenta"],
                archivo=datos["archivo"], referencia=pago.referencia, comentario=datos["observaciones"],
                periodos_solicitados=[{"anio": cuota.anio, "mes": cuota.mes}],
            )
            item.full_clean()
            item.save()
            ComprobanteCuota.objects.create(comprobante=item, cuota=cuota)
            registrar_auditoria(usuario=usuario, accion="REGISTRO_COMPROBANTE_TESORERIA", objeto=item,
                                descripcion=f"Comprobante registrado por Tesorería. Recibo {pago.numero_recibo}.")
            return pago
    except Exception:
        if item is not None and item.archivo and item.archivo._committed:
            item.archivo.delete(save=False)
        raise


@transaction.atomic
def revisar_comprobante(pk, datos, usuario):
    item = ComprobantePago.objects.select_for_update().get(pk=pk)
    if item.pago_id or item.estado == ComprobantePago.Estado.APROBADO:
        raise ValidationError('Este comprobante ya está registrado. No se puede volver a aplicar ni cambiar su período desde esta solicitud.')
    item.referencia = datos.get("referencia", item.referencia).strip()
    anteriores = list(item.cuotas.order_by('anio', 'mes').values('anio', 'mes'))
    if not item.periodos_solicitados:
        item.periodos_solicitados = anteriores
    anio, mes = datos.get('anio'), datos.get('mes')
    if not anio and not mes and not anteriores and len(item.periodos_solicitados) == 1 and datos['estado'] == ComprobantePago.Estado.APROBADO:
        periodo = item.periodos_solicitados[0]
        anio, mes = periodo['anio'], periodo['mes']
    if anio and mes:
        if item.casa.responsable_actual_id != item.responsable_id:
            raise ValidationError('El responsable de la casa cambió. Revisa la asignación antes de modificar el período.')
        cuota = asegurar_cuota(casa=item.casa, anio=anio, mes=mes, usuario=usuario)
        if cuota.responsable_id != item.responsable_id or cuota.colonia_id != item.colonia_id:
            raise ValidationError('El período no corresponde a este residente.')
        item.conceptos.all().delete()
        ComprobanteCuota.objects.create(comprobante=item, cuota=cuota)
    if datos['estado'] == ComprobantePago.Estado.APROBADO:
        cuotas = list(CuotaMensual.objects.select_for_update().filter(comprobantes=item, saldo__gt=0,
            responsable_id=item.responsable_id, colonia_id=item.colonia_id).exclude(estado=CuotaMensual.Estado.ANULADA).order_by('anio', 'mes', 'pk'))
        restante = item.monto
        aplicaciones = []
        for cuota in cuotas:
            monto = min(cuota.saldo, restante)
            if monto > Decimal('0'):
                aplicaciones.append({'cuota_id': cuota.pk, 'monto': monto})
                restante -= monto
        if restante > 0:
            raise ValidationError('El monto supera el saldo disponible del período seleccionado. No se registró ningún pago.')
        item.pago = registrar_pago(casa=item.casa, responsable=item.responsable, fecha_pago=item.fecha_pago,
            monto_total=item.monto, metodo_pago=item.metodo_pago, referencia=item.referencia,
            observaciones=f'Generado al aprobar comprobante #{item.pk}.', aplicaciones=aplicaciones, usuario=usuario)
    anterior = item.estado
    item.estado = datos['estado']
    item.comentario_revision = datos['comentario_revision']
    item.revisado_por = usuario
    item.revisado_en = timezone.now()
    item.save()
    registrar_auditoria(usuario=usuario, accion='REVISION_COMPROBANTE', objeto=item,
        descripcion=f'Comprobante cambiado de {anterior} a {item.estado}.',
        anteriores={'estado':anterior, 'periodos':anteriores},
        nuevos={'estado':item.estado, 'periodos':list(item.cuotas.values('anio','mes'))})
    return item


@transaction.atomic
def enviar_estado_comprobante(pk, usuario):
    """Only notify: never modifies approval, period, payment or balances."""
    item = ComprobantePago.objects.select_for_update().get(pk=pk)
    destinatario = item.correo_residente
    if not destinatario:
        return 'sin_correo', 'El residente no tiene correo registrado; no se envió correo.'
    try:
        validate_email(destinatario)
    except ValidationError:
        return 'error', 'El correo del residente no es válido. Corrígelo antes de enviar.'
    if item.correo_enviado_en and item.correo_estado == item.estado_notificacion and item.correo_enviado_en > timezone.now()-timedelta(seconds=30):
        return 'reciente', 'El correo de este estado ya se envió hace unos segundos.'
    smtp = settings.EMAIL_BACKEND == 'django.core.mail.backends.smtp.EmailBackend'
    if smtp and (not settings.EMAIL_HOST or not settings.DEFAULT_FROM_EMAIL):
        item.correo_error = 'Falta configurar el servidor de correo y su remitente.'
        item.save(update_fields=['correo_error'])
        return 'error', item.correo_error
    periodos = ', '.join(c.periodo for c in item.cuotas.order_by('anio','mes')) or 'Sin período asignado'
    estado = item.estado_visible
    body = (f'Hola, {item.responsable.nombre_completo}.\n\n'
        f'Estado de tu comprobante #{item.pk}: {estado}.\n'
        f'Residencial: {item.colonia.nombre}\nCasa: {item.casa.codigo}\n'
        f'Monto: L {item.monto:.2f}\nPeríodo: {periodos}\n'
        f'Comentario de tesorería: {item.comentario_revision or "Sin comentario"}\n\nResidencial Segura')
    try:
        sent = send_mail(f'Residencial Segura · Comprobante #{item.pk}: {estado}', body,
                         settings.DEFAULT_FROM_EMAIL, [destinatario], fail_silently=False)
        if sent != 1: raise RuntimeError('Mail not accepted')
    except Exception:
        item.correo_error = 'No se pudo enviar el correo. Puedes reintentar con Enviar correo.'
        item.save(update_fields=['correo_error'])
        return 'error', item.correo_error
    item.correo_enviado_en = timezone.now()
    item.correo_estado = item.estado_notificacion
    item.correo_error = ''
    item.save(update_fields=['correo_enviado_en','correo_estado','correo_error'])
    registrar_auditoria(usuario=usuario, accion='CORREO_COMPROBANTE', objeto=item,
                       descripcion=f'Correo de estado {item.estado_notificacion} aceptado por el servidor de correo.')
    return 'enviado', 'Correo enviado al residente.'
