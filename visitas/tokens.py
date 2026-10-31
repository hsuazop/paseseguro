import time

from django.core import signing


SALT_RESIDENTE = "paseseguro.qr-residente"
VENTANA_SEGUNDOS = 30


def crear_token_residente(*, usuario_id, casa_id, instante=None):
    bloque = int((instante or time.time()) // VENTANA_SEGUNDOS)
    payload = {"u": usuario_id, "c": casa_id, "b": bloque}
    return signing.dumps(payload, salt=SALT_RESIDENTE, compress=True)


def leer_token_residente(token, max_age=65):
    return signing.loads(token, salt=SALT_RESIDENTE, max_age=max_age)

