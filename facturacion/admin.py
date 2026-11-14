from django.contrib import admin
from django import forms
from django.urls import reverse
from django.utils.html import format_html
from core.admin_utils import BaseAdmin, ReadOnlyAdmin

from .models import (
    AplicacionPago,
    ComprobanteCuota,
    ComprobantePago,
    CuentaPagoColonia,
    CuotaMensual,
    Pago,
    ReciboSecuencia,
    TarifaColonia,
    TarifaEspecialCasa,
)


@admin.register(TarifaColonia)
class TarifaColoniaAdmin(BaseAdmin):
    list_display = ("colonia", "monto", "fecha_inicio", "fecha_fin", "activa")
    list_filter = ("colonia", "activa")
    search_fields = ("colonia__nombre",)
    autocomplete_fields = ("colonia",)
    list_select_related = ("colonia",)
    date_hierarchy = "fecha_inicio"


@admin.register(TarifaEspecialCasa)
class TarifaEspecialCasaAdmin(BaseAdmin):
    list_display = ("casa", "tipo", "monto", "porcentaje", "fecha_inicio", "fecha_fin", "activa")
    list_filter = ("tipo", "activa", "casa__colonia")
    search_fields = ("casa__codigo", "casa__colonia__nombre", "motivo")
    autocomplete_fields = ("casa", "usuario_que_autoriza")
    list_select_related = ("casa__colonia",)
    date_hierarchy = "fecha_inicio"


class CuotaAdminForm(forms.ModelForm):
    class Meta:
        model = CuotaMensual
        fields = "__all__"

    def clean(self):
        data = super().clean()
        casa, colonia, responsable = data.get("casa"), data.get("colonia"), data.get("responsable")
        if not self.instance.pk and casa:
            if colonia and casa.colonia_id != colonia.pk:
                self.add_error("colonia", "La casa pertenece a otra residencial.")
            if responsable and casa.responsable_actual_id != responsable.pk:
                self.add_error("responsable", "Selecciona al responsable actual de esta casa.")
        return data


@admin.register(CuotaMensual)
class CuotaMensualAdmin(BaseAdmin):
    form = CuotaAdminForm
    list_display = ("responsable", "colonia", "codigo_casa", "anio", "mes", "monto_original", "monto_pagado", "saldo", "estado")
    list_filter = ("estado", "anio", "mes", "colonia")
    search_fields = ("responsable__nombre_completo", "responsable__identidad", "casa__codigo")
    readonly_fields = ("monto_pagado", "saldo", "estado")
    autocomplete_fields = ("responsable", "colonia", "casa")
    list_select_related = ("responsable", "colonia", "casa__colonia")
    ordering = ("-anio", "-mes", "responsable__nombre_completo")

    @admin.display(description="Casa", ordering="casa__codigo")
    def codigo_casa(self, obj):
        return obj.casa.codigo

    def get_readonly_fields(self, request, obj=None):
        fields = super().get_readonly_fields(request, obj)
        if obj:
            fields += ("colonia", "casa", "responsable", "anio", "mes", "monto_original")
        return fields

    def save_model(self, request, obj, form, change):
        if not change:
            obj.saldo = obj.monto_original
        super().save_model(request, obj, form, change)

    def has_delete_permission(self, request, obj=None):
        return False


class AplicacionPagoInline(admin.TabularInline):
    model = AplicacionPago
    extra = 0
    readonly_fields = ("cuota_mensual", "monto_aplicado")
    can_delete = False
    show_change_link = True

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Pago)
class PagoAdmin(ReadOnlyAdmin):
    list_display = ("numero_recibo", "fecha_pago", "casa", "responsable", "monto_total", "metodo_pago", "anulado", "operaciones")
    list_filter = ("anulado", "metodo_pago", "fecha_pago", "colonia")
    search_fields = ("numero_recibo", "casa__codigo", "responsable__nombre_completo")
    readonly_fields = tuple(field.name for field in Pago._meta.fields)
    inlines = (AplicacionPagoInline,)
    date_hierarchy = "fecha_pago"
    list_select_related = ("casa__colonia", "responsable", "colonia", "usuario_que_registra")

    @admin.display(description="Operaciones")
    def operaciones(self, obj):
        if obj.anulado:
            return format_html('<a href="{}">Ver recibo</a>', reverse("recibo_detalle", args=[obj.pk]))
        return format_html('<a href="{}">Ver recibo</a> · <a href="{}">Anular pago</a>',
                           reverse("recibo_detalle", args=[obj.pk]), reverse("pago_anular", args=[obj.pk]))

    def get_readonly_fields(self, request, obj=None):
        return (*super().get_readonly_fields(request, obj), "operaciones")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ReciboSecuencia)
class ReciboSecuenciaAdmin(ReadOnlyAdmin):
    list_display = ("anio", "ultimo_numero")
    list_filter = ("anio",)
    search_fields = ("=anio",)
    ordering = ("-anio",)


@admin.register(CuentaPagoColonia)
class CuentaPagoColoniaAdmin(BaseAdmin):
    list_display = ("banco", "numero_cuenta", "titular", "colonia", "tipo_cuenta", "activa")
    list_filter = ("colonia", "activa", "banco")
    search_fields = ("banco", "numero_cuenta", "titular", "identidad_titular", "colonia__nombre")
    autocomplete_fields = ("colonia",)
    list_select_related = ("colonia",)


class ComprobanteCuotaInline(admin.TabularInline):
    model = ComprobanteCuota
    extra = 0
    readonly_fields = ("cuota",)
    can_delete = False
    show_change_link = True

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(ComprobantePago)
class ComprobantePagoAdmin(ReadOnlyAdmin):
    inlines = (ComprobanteCuotaInline,)
    list_display = ("id", "casa", "responsable", "monto", "fecha_pago", "metodo_pago", "estado", "operaciones")
    list_filter = ("estado", "metodo_pago", "colonia")
    search_fields = ("casa__codigo", "responsable__nombre_completo", "referencia")
    readonly_fields = ("enviado_por", "revisado_por", "revisado_en", "pago")
    list_select_related = ("casa__colonia", "responsable", "colonia", "enviado_por", "revisado_por", "pago")
    date_hierarchy = "fecha_pago"

    @admin.display(description="Revisión")
    def operaciones(self, obj):
        return format_html('<a href="{}">Revisar comprobante</a>', reverse("comprobante_revisar", args=[obj.pk]))

    def get_readonly_fields(self, request, obj=None):
        return (*super().get_readonly_fields(request, obj), "operaciones")


@admin.register(AplicacionPago)
class AplicacionPagoAdmin(ReadOnlyAdmin):
    list_display = ("pago", "cuota_mensual", "monto_aplicado", "created_at")
    list_filter = ("cuota_mensual__colonia", "cuota_mensual__anio", "cuota_mensual__mes", "pago__anulado")
    search_fields = ("pago__numero_recibo", "cuota_mensual__responsable__nombre_completo", "cuota_mensual__casa__codigo")
    list_select_related = ("pago", "cuota_mensual__casa__colonia")
    date_hierarchy = "created_at"


@admin.register(ComprobanteCuota)
class ComprobanteCuotaAdmin(ReadOnlyAdmin):
    list_display = ("comprobante", "cuota")
    list_filter = ("cuota__colonia", "cuota__anio", "cuota__mes", "comprobante__estado")
    search_fields = ("=comprobante__pk", "cuota__responsable__nombre_completo", "cuota__casa__codigo")
    list_select_related = ("comprobante__casa__colonia", "cuota__casa__colonia")
