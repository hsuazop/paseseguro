from django.urls import path

from . import views


urlpatterns = [
    path("mi-cuenta/<int:casa_id>/visitas/", views.visitas_lista, name="visitas_lista"),
    path("mi-cuenta/<int:casa_id>/visitas/nueva/", views.visita_crear, name="visita_crear"),
    path("mi-cuenta/<int:casa_id>/visitas/<int:pk>/", views.visita_detalle, name="visita_detalle"),
    path("mi-cuenta/<int:casa_id>/visitas/<int:pk>/cancelar/", views.visita_cancelar, name="visita_cancelar"),
    path("mi-cuenta/<int:casa_id>/mi-qr/", views.qr_residente, name="qr_residente"),
    path("mi-cuenta/<int:casa_id>/mi-qr/token/", views.token_qr_residente, name="token_qr_residente"),
    path("accesos/residente/<str:token>/", views.verificar_qr_residente, name="verificar_qr_residente"),
    path("accesos/visita/<uuid:token>/", views.visita_publica, name="visita_publica"),
    path("control/visitas/", views.visitas_control, name="visitas_control"),
    path("control/visitas/<int:pk>/entrada/", views.visita_registrar_acceso, name="visita_registrar_acceso"),
]
