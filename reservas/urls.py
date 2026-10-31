from django.urls import path

from . import views


urlpatterns = [
    path("mi-cuenta/<int:casa_id>/reservaciones/", views.areas_lista, name="areas_lista"),
    path("mi-cuenta/<int:casa_id>/reservaciones/nueva/", views.reserva_crear, name="reserva_crear"),
    path(
        "mi-cuenta/<int:casa_id>/reservaciones/area/<int:area_id>/",
        views.reserva_crear,
        name="reserva_area_crear",
    ),
    path("mi-cuenta/<int:casa_id>/reservaciones/<int:pk>/cancelar/", views.reserva_cancelar, name="reserva_cancelar"),
    path("reservaciones/gestion/", views.reservas_gestion, name="reservas_gestion"),
    path("reservaciones/gestion/<int:pk>/", views.reserva_revisar, name="reserva_revisar"),
    path("reservaciones/areas/nueva/", views.area_crear, name="area_crear"),
]
