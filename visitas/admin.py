from django.contrib import admin

from .models import RegistroAcceso, Visita


@admin.register(Visita)
class VisitaAdmin(admin.ModelAdmin):
    list_display = ("nombre_visitante", "casa", "fecha_inicio", "max_usos", "usos_actuales", "activa")
    list_filter = ("tipo", "temporalidad", "activa", "casa__colonia")
    search_fields = ("nombre_visitante", "identidad_visitante", "clave_acceso", "casa__codigo")


@admin.register(RegistroAcceso)
class RegistroAccesoAdmin(admin.ModelAdmin):
    list_display = ("visita", "personas", "registrado_por", "created_at")

