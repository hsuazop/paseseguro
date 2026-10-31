from django.contrib import admin

from .models import AreaComun, Reserva


@admin.register(AreaComun)
class AreaComunAdmin(admin.ModelAdmin):
    list_display = ("nombre", "colonia", "capacidad", "costo", "activa")
    list_filter = ("colonia", "activa")


@admin.register(Reserva)
class ReservaAdmin(admin.ModelAdmin):
    list_display = ("area", "casa", "fecha", "hora_inicio", "hora_fin", "estado")
    list_filter = ("estado", "area__colonia", "fecha")

