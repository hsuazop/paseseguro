from django.contrib import admin
from core.admin_utils import BaseAdmin

from .models import CasaResponsable, Responsable


@admin.register(Responsable)
class ResponsableAdmin(BaseAdmin):
    list_display = ("nombre_completo", "identidad", "telefono", "correo", "usuario", "activo")
    search_fields = ("nombre_completo", "identidad", "telefono", "correo", "usuario__username")
    list_filter = ("activo",)
    autocomplete_fields = ("usuario", "creado_por")
    list_select_related = ("usuario",)
    fieldsets = (("Datos personales", {"fields": ("nombre_completo", "identidad", "activo")}),
                 ("Contacto", {"fields": ("telefono", "correo")}),
                 ("Cuenta y registro", {"fields": ("usuario", "creado_por", "created_at", "updated_at")}))


@admin.register(CasaResponsable)
class CasaResponsableAdmin(BaseAdmin):
    list_display = ("casa", "responsable", "fecha_inicio", "fecha_fin", "activo")
    list_filter = ("activo", "casa__colonia")
    search_fields = ("casa__codigo", "casa__colonia__nombre", "responsable__nombre_completo", "responsable__identidad")
    autocomplete_fields = ("casa", "responsable")
    list_select_related = ("casa__colonia", "responsable")
    date_hierarchy = "fecha_inicio"
