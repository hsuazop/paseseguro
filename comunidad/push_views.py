import base64
import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit
from django.conf import settings
from django.http import JsonResponse, HttpResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.views.decorators.http import require_POST, require_GET
from django.views.decorators.cache import never_cache
from django.db import transaction
from django.utils import timezone
from accounts.permissions import roles_requeridos, colonias_permitidas
from .models import AlertaSOS, SuscripcionPush


def servicio_worker(request):
    response = HttpResponse((Path(__file__).parent / 'service-worker.js').read_text(encoding='utf-8'), content_type='application/javascript')
    response['Cache-Control'] = 'no-cache'
    response['Service-Worker-Allowed'] = '/'
    return response


@roles_requeridos('GUARDIA')
@never_cache
@require_GET
def configuracion(request):
    return JsonResponse({'publicKey': settings.WEBPUSH_PUBLIC_KEY, 'configured': bool(settings.WEBPUSH_PUBLIC_KEY and settings.WEBPUSH_PRIVATE_KEY and settings.WEBPUSH_SUBJECT)})


@roles_requeridos('GUARDIA')
@require_POST
def suscribir(request):
    if request.user.rol != 'GUARDIA':
        return JsonResponse({'error': 'Se requiere una cuenta de guardia.'}, status=403)
    try:
        if len(request.body) > 5000: raise ValueError()
        data = json.loads(request.body)
        endpoint = data['endpoint']
        url = urlsplit(endpoint)
        host = url.hostname or ''
        allowed = host in ('fcm.googleapis.com', 'updates.push.services.mozilla.com', 'web.push.apple.com') or host.endswith('.notify.windows.com')
        if not allowed or url.scheme != 'https' or url.port not in (None, 443) or url.username or url.password or url.fragment or len(endpoint)>2048:
            raise ValueError()
        keys = {key: data['keys'][key] for key in ('p256dh', 'auth')}
        for key,size in (('p256dh',65), ('auth',16)):
            value = keys[key]
            decoded = base64.urlsafe_b64decode(value+'='*((-len(value))%4))
            if len(decoded) != size: raise ValueError()
        payload = {'endpoint': endpoint, 'keys': keys}
    except (ValueError, TypeError, KeyError, AttributeError):
        return JsonResponse({'error': 'Suscripción inválida.'}, status=400)
    SuscripcionPush.objects.update_or_create(endpoint_hash=hashlib.sha256(endpoint.encode()).hexdigest(), defaults={'usuario':request.user, 'session_key':request.session.session_key, 'datos':payload, 'activa':True})
    return JsonResponse({'ok': True})


@roles_requeridos('GUARDIA')
@require_POST
def desactivar(request):
    SuscripcionPush.objects.filter(usuario=request.user, session_key=request.session.session_key).update(activa=False)
    return JsonResponse({'ok':True})


def alertas_usuario(user):
    return AlertaSOS.objects.filter(colonia__in=colonias_permitidas(user)).select_related('usuario','casa','colonia','atendido_por')


@roles_requeridos('GUARDIA')
@never_cache
@require_GET
def datos_alerta(request, pk):
    alerta = get_object_or_404(alertas_usuario(request.user), pk=pk)
    if alerta.estado != 'NUEVA': return JsonResponse({'active':False})
    return JsonResponse({'active':True,'id':alerta.pk,'title':f'SOS · Casa {alerta.casa.codigo}', 'body':f'{alerta.usuario.nombre_completo} · {alerta.colonia.nombre} · Casa {alerta.casa.codigo}', 'url':f'/guardia/sos/{alerta.pk}/'})


@roles_requeridos('GUARDIA')
@never_cache
@require_GET
def lista(request):
    alerts = alertas_usuario(request.user).exclude(estado='CERRADA')
    if request.GET.get('format') == 'json':
        return JsonResponse({'alertas':[{'id':a.pk,'nombre':a.usuario.nombre_completo,'casa':a.casa.codigo,'estado':a.estado} for a in alerts[:100]]})
    return render(request,'comunidad/sos_guardia.html',{'alertas':alerts[:100]})


@roles_requeridos('GUARDIA')
@never_cache
def detalle(request, pk):
    alerta = get_object_or_404(alertas_usuario(request.user), pk=pk)
    if request.method == 'POST':
        action = request.POST.get('accion')
        with transaction.atomic():
            alerta = AlertaSOS.objects.select_for_update().get(pk=alerta.pk)
            if action == 'atender' and alerta.estado == 'NUEVA':
                alerta.estado='ATENDIENDO'; alerta.atendido_por=request.user; alerta.atendido_en=timezone.now()
                alerta.save(update_fields=['estado','atendido_por','atendido_en','updated_at'])
            elif action == 'cerrar' and alerta.estado == 'ATENDIENDO' and (alerta.atendido_por_id==request.user.pk or request.user.is_superuser):
                alerta.estado='CERRADA';alerta.save(update_fields=['estado','updated_at'])
        return redirect('sos_guardia_detalle',pk=pk)
    return render(request,'comunidad/sos_guardia_detalle.html',{'alerta':alerta})
