"""Session-scoped Web Push and durable SOS deliveries. Run the worker continuously."""
import json
from datetime import timedelta
from django.conf import settings
from django.contrib.sessions.models import Session
from django.db import transaction
from django.utils import timezone
from django.utils.crypto import constant_time_compare
from accounts.permissions import colonias_permitidas
from .models import SuscripcionPush, EntregaSOS


def habilitada(sub, colonia_id):
    user = sub.usuario
    if not sub.activa or not user.is_active or user.rol != 'GUARDIA' or user.debe_cambiar_password:
        return False
    session = Session.objects.filter(session_key=sub.session_key, expire_date__gt=timezone.now()).first()
    data = session.get_decoded() if session else {}
    return (str(data.get('_auth_user_id')) == str(user.pk)
            and constant_time_compare(data.get('_auth_user_hash', ''), user.get_session_auth_hash())
            and colonias_permitidas(user).filter(pk=colonia_id).exists())


def encolar(alerta):
    for sub in SuscripcionPush.objects.filter(activa=True, usuario__rol='GUARDIA', usuario__is_active=True).select_related('usuario'):
        if habilitada(sub, alerta.colonia_id):
            EntregaSOS.objects.get_or_create(alerta=alerta, suscripcion=sub)


def procesar_lote():
    from pywebpush import webpush, WebPushException
    if not all((settings.WEBPUSH_PRIVATE_KEY, settings.WEBPUSH_PUBLIC_KEY, settings.WEBPUSH_SUBJECT)):
        return 0
    processed = 0
    for pk in EntregaSOS.objects.filter(estado='PENDIENTE', siguiente__lte=timezone.now()).values_list('pk', flat=True)[:50]:
        # A row lock avoids duplicate sends with multiple workers. Network timeout is bounded.
        with transaction.atomic():
            item = EntregaSOS.objects.select_for_update().select_related('alerta', 'suscripcion__usuario').get(pk=pk)
            if item.estado != 'PENDIENTE' or item.siguiente > timezone.now():
                continue
            sub = item.suscripcion
            if item.alerta.estado != 'NUEVA' or item.alerta.created_at < timezone.now()-timedelta(minutes=15) or not habilitada(sub, item.alerta.colonia_id):
                item.estado = 'CANCELADA'
            else:
                item.intentos += 1
                try:
                    webpush(subscription_info=sub.datos, data=json.dumps({'alerta': item.alerta_id}),
                            vapid_private_key=settings.WEBPUSH_PRIVATE_KEY,
                            vapid_claims={'sub': settings.WEBPUSH_SUBJECT}, ttl=120,
                            headers={'Urgency': 'high'}, timeout=10)
                    item.estado = 'ACEPTADA'  # Push provider accepted, not proof of device receipt.
                    item.codigo_error = ''
                except Exception as exc:
                    response = getattr(exc, 'response', None)
                    status = getattr(response, 'status_code', None)
                    item.codigo_error = str(status or type(exc).__name__)[:40]
                    if status in (404, 410):
                        sub.activa = False
                        sub.save(update_fields=['activa'])
                    if status in (400, 401, 403, 404, 410) or item.intentos >= 5:
                        item.estado = 'FALLIDA'
                    else:
                        item.siguiente = timezone.now()+timedelta(seconds=min(120, 5*2**item.intentos))
            item.save()
            processed += 1
    return processed
