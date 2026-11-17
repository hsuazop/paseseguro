from django.urls import path

from . import views
from . import padron_views


urlpatterns = [
    path('vehiculos-residencial/', padron_views.lista, name='padron_vehicular'),
    path('vehiculos-residencial/nuevo/', padron_views.formulario, name='padron_vehicular_crear'),
    path('vehiculos-residencial/<int:pk>/editar/', padron_views.formulario, name='padron_vehicular_editar'),
    path("guardia/", views.dashboard_guardia, name="dashboard_guardia"),
    path("guardia/entrada/", views.registrar_entrada, name="registrar_entrada"),
    path("guardia/salida/<int:pk>/", views.registrar_salida, name="registrar_salida"),
    path("guardia/historial/", views.historial_accesos, name="historial_accesos"),
    path("mi-cuenta/<int:casa_id>/vehiculos/", views.mis_vehiculos, name="mis_vehiculos"),
    path("mi-cuenta/<int:casa_id>/vehiculos/nuevo/", views.vehiculo_crear, name="vehiculo_crear"),
]
