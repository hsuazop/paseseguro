from django.urls import path

from . import views


urlpatterns = [
    path("guardia/", views.dashboard_guardia, name="dashboard_guardia"),
    path("guardia/entrada/", views.registrar_entrada, name="registrar_entrada"),
    path("guardia/salida/<int:pk>/", views.registrar_salida, name="registrar_salida"),
    path("guardia/historial/", views.historial_accesos, name="historial_accesos"),
    path("mi-cuenta/<int:casa_id>/vehiculos/", views.mis_vehiculos, name="mis_vehiculos"),
    path("mi-cuenta/<int:casa_id>/vehiculos/nuevo/", views.vehiculo_crear, name="vehiculo_crear"),
]
