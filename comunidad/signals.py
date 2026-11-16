from django.contrib.auth.signals import user_logged_out
from django.dispatch import receiver
from .models import SuscripcionPush

@receiver(user_logged_out)
def cerrar_push(sender, request, user, **kwargs):
    if request and user:
        SuscripcionPush.objects.filter(usuario=user, session_key=request.session.session_key).update(activa=False)
