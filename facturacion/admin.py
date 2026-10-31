from django.contrib import admin

from .models import (
    AplicacionPago,
    ComprobantePago,
    CuentaPagoColonia,
    CuotaMensual,
    Pago,
    ReciboSecuencia,
    TarifaColonia,
    TarifaEspecialCasa,
)


@admin.register(TarifaColonia)
class TarifaColoniaAdmin(admin.ModelAdmin):
    list_display = ("colonia", "monto", "fecha_inicio", "fecha_fin", "activa")
    list_filter = ("colonia", "activa")


@admin.register(TarifaEspecialCasa)
class TarifaEspecialCasaAdmin(admin.ModelAdmin):
    list_display = ("casa", "tipo", "monto", "porcentaje", "fecha_inicio", "fecha_fin", "activa")
    list_filter = ("tipo", "activa", "casa__colonia")


@admin.register(CuotaMensual)
class CuotaMensualAdmin(admin.ModelAdmin):
    list_display = ("responsable", "colonia", "casa", "anio", "mes", "monto_original", "monto_pagado", "saldo", "estado")
    list_filter = ("estado", "anio", "mes", "colonia")
    search_fields = ("responsable__nombre_completo", "responsable__identidad", "casa__codigo")
    readonly_fields = ("monto_pagado", "saldo", "estado")


class AplicacionPagoInline(admin.TabularInline):
    model = AplicacionPago
    extra = 0
    readonly_fields = ("cuota_mensual", "monto_aplicado")
    can_delete = False


@admin.register(Pago)
class PagoAdmin(admin.ModelAdmin):
    list_display = ("numero_recibo", "fecha_pago", "casa", "responsable", "monto_total", "metodo_pago", "anulado")
    list_filter = ("anulado", "metodo_pago", "fecha_pago", "colonia")
    search_fields = ("numero_recibo", "casa__codigo", "responsable__nombre_completo")
    readonly_fields = tuple(field.name for field in Pago._meta.fields)
    inlines = (AplicacionPagoInline,)

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.register(ReciboSecuencia)
admin.site.register(CuentaPagoColonia)


@admin.register(ComprobantePago)
class ComprobantePagoAdmin(admin.ModelAdmin):
    list_display = ("id", "casa", "monto", "fecha_pago", "metodo_pago", "estado", "created_at")
    list_filter = ("estado", "metodo_pago", "colonia")
    search_fields = ("casa__codigo", "responsable__nombre_completo", "referencia")
    readonly_fields = ("enviado_por", "revisado_por", "revisado_en", "pago")
