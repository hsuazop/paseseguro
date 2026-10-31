from django.contrib import admin

from .models import Casa, Colonia


@admin.register(Colonia)
class ColoniaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "telefono", "activa", "created_at")
    list_filter = ("activa",)
    search_fields = ("nombre", "direccion")


@admin.register(Casa)
class CasaAdmin(admin.ModelAdmin):
    list_display = ("codigo", "numero", "colonia", "responsable_actual", "activa")
    list_filter = ("colonia", "activa")
    search_fields = ("codigo", "numero", "responsable_actual__nombre_completo")
