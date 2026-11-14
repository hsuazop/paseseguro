from django.contrib import admin
from core.admin_utils import BaseAdmin

from .models import AlertaSOS, Clasificado, Comunicado, DirectorioEntrada, DocumentoComunidad, SolicitudMensaje


@admin.register(SolicitudMensaje)
class SolicitudMensajeAdmin(BaseAdmin):
    list_display = ("asunto", "tipo", "casa", "visibilidad", "estado", "created_at")
    list_filter = ("tipo", "visibilidad", "estado", "colonia")
    search_fields = ("asunto", "mensaje", "casa__codigo", "usuario__username")
    autocomplete_fields = ("colonia", "casa", "usuario", "respondido_por")
    list_select_related = ("colonia", "casa__colonia", "usuario", "respondido_por")
    date_hierarchy = "created_at"


@admin.register(AlertaSOS)
class AlertaSOSAdmin(BaseAdmin):
    list_display = ("casa", "usuario", "estado", "created_at")
    list_filter = ("estado", "colonia")
    search_fields = ("mensaje", "casa__codigo", "usuario__username", "colonia__nombre")
    autocomplete_fields = ("colonia", "casa", "usuario")
    list_select_related = ("colonia", "casa__colonia", "usuario")
    date_hierarchy = "created_at"


@admin.register(Comunicado)
class ComunicadoAdmin(BaseAdmin):
    list_display = ("titulo", "colonia", "publicado_por", "publicado_en", "activo")
    list_filter = ("colonia", "activo", "publicado_en")
    search_fields = ("titulo", "contenido", "colonia__nombre", "publicado_por__username")
    autocomplete_fields = ("colonia", "publicado_por")
    list_select_related = ("colonia", "publicado_por")
    date_hierarchy = "publicado_en"


@admin.register(Clasificado)
class ClasificadoAdmin(BaseAdmin):
    list_display = ("titulo", "colonia", "usuario", "precio", "telefono", "activo", "created_at")
    list_filter = ("colonia", "activo", "created_at")
    search_fields = ("titulo", "descripcion", "telefono", "usuario__username", "colonia__nombre")
    autocomplete_fields = ("colonia", "usuario")
    list_select_related = ("colonia", "usuario")
    date_hierarchy = "created_at"


@admin.register(DirectorioEntrada)
class DirectorioEntradaAdmin(BaseAdmin):
    list_display = ("nombre", "categoria", "telefono", "colonia", "activo")
    list_filter = ("colonia", "categoria", "activo")
    search_fields = ("nombre", "categoria", "telefono", "descripcion", "colonia__nombre")
    autocomplete_fields = ("colonia",)
    list_select_related = ("colonia",)


@admin.register(DocumentoComunidad)
class DocumentoComunidadAdmin(BaseAdmin):
    list_display = ("titulo", "colonia", "activo", "created_at")
    list_filter = ("colonia", "activo", "created_at")
    search_fields = ("titulo", "descripcion", "colonia__nombre")
    autocomplete_fields = ("colonia",)
    list_select_related = ("colonia",)
    date_hierarchy = "created_at"

