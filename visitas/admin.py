from django.contrib import admin
from core.admin_utils import BaseAdmin

from .models import RegistroAcceso, Visita


@admin.register(Visita)
class VisitaAdmin(BaseAdmin):
    list_display = ("nombre_visitante", "casa", "fecha_inicio", "max_usos", "usos_actuales", "activa")
    list_filter = ("tipo", "temporalidad", "activa", "casa__colonia")
    search_fields = ("nombre_visitante", "identidad_visitante", "clave_acceso", "casa__codigo")
    autocomplete_fields = ("casa", "creado_por")
    readonly_fields = ("clave_acceso", "token_publico", "usos_actuales")
    list_select_related = ("casa__colonia", "creado_por")
    date_hierarchy = "fecha_inicio"


@admin.register(RegistroAcceso)
class RegistroAccesoAdmin(BaseAdmin):
    list_display = ("visita", "personas", "registrado_por", "created_at")
    list_filter = ("visita__casa__colonia", "created_at")
    search_fields = ("visita__nombre_visitante", "visita__casa__codigo", "registrado_por__username", "observacion")
    autocomplete_fields = ("visita", "registrado_por")
    list_select_related = ("visita__casa__colonia", "registrado_por")
    date_hierarchy = "created_at"

