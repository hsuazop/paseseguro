from django.contrib import admin
from core.admin_utils import BaseAdmin

from .models import Casa, Colonia


@admin.register(Colonia)
class ColoniaAdmin(BaseAdmin):
    list_display = ("nombre", "telefono", "activa", "created_at")
    list_filter = ("activa",)
    search_fields = ("nombre", "direccion", "telefono")
    date_hierarchy = "created_at"
    fieldsets = (("Residencial", {"fields": ("nombre", "descripcion", "activa")}),
                 ("Contacto y ubicación", {"fields": ("direccion", "telefono")}),
                 ("Registro", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}))


@admin.register(Casa)
class CasaAdmin(BaseAdmin):
    list_display = ("codigo", "numero", "colonia", "responsable_actual", "activa")
    list_filter = ("colonia", "activa")
    search_fields = ("codigo", "numero", "bloque", "calle", "colonia__nombre", "responsable_actual__nombre_completo", "responsable_actual__identidad")
    autocomplete_fields = ("colonia", "responsable_actual")
    list_select_related = ("colonia", "responsable_actual")
    fieldsets = (("Identificación", {"fields": ("colonia", "codigo", "numero", "activa")}),
                 ("Ubicación", {"fields": ("bloque", "calle", "referencia")}),
                 ("Responsable", {"fields": ("responsable_actual",)}),
                 ("Registro", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}))
