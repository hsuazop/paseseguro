from django.contrib import admin
from core.admin_utils import BaseAdmin

from .models import AreaComun, Reserva


@admin.register(AreaComun)
class AreaComunAdmin(BaseAdmin):
    list_display = ("nombre", "colonia", "capacidad", "costo", "activa")
    list_filter = ("colonia", "activa")
    search_fields = ("nombre", "descripcion", "colonia__nombre")
    autocomplete_fields = ("colonia",)
    list_select_related = ("colonia",)


@admin.register(Reserva)
class ReservaAdmin(BaseAdmin):
    list_display = ("area", "casa", "fecha", "hora_inicio", "hora_fin", "estado")
    list_filter = ("estado", "area__colonia", "fecha")
    search_fields = ("area__nombre", "casa__codigo", "usuario__username", "motivo")
    autocomplete_fields = ("area", "casa", "usuario", "revisado_por")
    list_select_related = ("area__colonia", "casa__colonia", "usuario", "revisado_por")
    date_hierarchy = "fecha"

