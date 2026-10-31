from django.contrib import admin

from .models import AlertaSOS, Clasificado, Comunicado, DirectorioEntrada, DocumentoComunidad, SolicitudMensaje


@admin.register(SolicitudMensaje)
class SolicitudMensajeAdmin(admin.ModelAdmin):
    list_display = ("asunto", "tipo", "casa", "visibilidad", "estado", "created_at")
    list_filter = ("tipo", "visibilidad", "estado", "colonia")
    search_fields = ("asunto", "mensaje", "casa__codigo", "usuario__username")


@admin.register(AlertaSOS)
class AlertaSOSAdmin(admin.ModelAdmin):
    list_display = ("casa", "usuario", "estado", "created_at")
    list_filter = ("estado", "colonia")


admin.site.register(Comunicado)
admin.site.register(Clasificado)
admin.site.register(DirectorioEntrada)
admin.site.register(DocumentoComunidad)

