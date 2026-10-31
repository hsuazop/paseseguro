from django.contrib import admin

from .models import CasaResponsable, Responsable


@admin.register(Responsable)
class ResponsableAdmin(admin.ModelAdmin):
    list_display = ("nombre_completo", "identidad", "telefono", "usuario", "activo")
    search_fields = ("nombre_completo", "identidad", "telefono")
    list_filter = ("activo",)


@admin.register(CasaResponsable)
class CasaResponsableAdmin(admin.ModelAdmin):
    list_display = ("casa", "responsable", "fecha_inicio", "fecha_fin", "activo")
    list_filter = ("activo", "casa__colonia")
