from .permissions import colonias_permitidas, ocultar_listado_pagos, puede_elegir_colonia


def contexto_colonia(request):
    seleccionable = puede_elegir_colonia(request.user)
    asignada = None
    if request.user.is_authenticated and not seleccionable:
        asignada = colonias_permitidas(request.user).first()
    return {
        "puede_elegir_colonia": seleccionable,
        "colonia_asignada": asignada,
        "ocultar_listado_pagos": ocultar_listado_pagos(request.user, asignada),
    }
