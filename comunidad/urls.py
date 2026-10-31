from django.urls import path

from . import views


urlpatterns = [
    path("mi-cuenta/<int:casa_id>/solicitudes/", views.solicitudes_lista, name="solicitudes_lista"),
    path("mi-cuenta/<int:casa_id>/solicitudes/nueva/", views.solicitud_crear, name="solicitud_crear"),
    path("mi-cuenta/<int:casa_id>/comunidad/", views.comunidad_muro, name="comunidad_muro"),
    path("mi-cuenta/<int:casa_id>/sos/", views.alerta_sos, name="alerta_sos"),
    path("mi-cuenta/<int:casa_id>/comunicados/", views.comunicados_lista, name="comunicados_lista"),
    path("mi-cuenta/<int:casa_id>/clasificados/", views.clasificados_lista, name="clasificados_lista"),
    path("mi-cuenta/<int:casa_id>/clasificados/nuevo/", views.clasificado_crear, name="clasificado_crear"),
    path("mi-cuenta/<int:casa_id>/directorio/", views.directorio_documentos, name="directorio_documentos"),
    path("comunidad/bandeja/", views.bandeja_comunidad, name="bandeja_comunidad"),
    path("comunidad/solicitudes/<int:pk>/responder/", views.solicitud_responder, name="solicitud_responder"),
    path("comunidad/comunicados/nuevo/", views.comunicado_crear, name="comunicado_crear"),
    path("comunidad/directorio/nuevo/", views.directorio_crear, name="directorio_crear"),
    path("comunidad/documentos/nuevo/", views.documento_crear, name="documento_crear"),
]
