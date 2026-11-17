from django.contrib import admin
from core.admin_utils import BaseAdmin

from .models import RegistroVehicular, Vehiculo, VehiculoColonia


@admin.register(VehiculoColonia)
class VehiculoColoniaAdmin(BaseAdmin):
    list_display = ('placa', 'propietario', 'telefono', 'marca_modelo', 'colonia', 'revisar', 'activo')
    list_filter = ('colonia', 'revisar', 'activo')
    search_fields = ('placa', 'propietario', 'telefono', 'marca_modelo', 'direccion')
    list_select_related = ('colonia',)
    readonly_fields = ('origen', 'clave_importacion')

    def get_queryset(self, request):
        from accounts.permissions import colonias_permitidas
        return super().get_queryset(request).filter(colonia__in=colonias_permitidas(request.user))

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'colonia':
            from accounts.permissions import colonias_permitidas
            kwargs['queryset'] = colonias_permitidas(request.user)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(Vehiculo)
class VehiculoAdmin(BaseAdmin):
    list_display = ("placa", "responsable", "casa", "marca", "modelo", "color", "activo")
    list_filter = ("colonia", "tipo", "activo")
    search_fields = ("placa", "responsable__nombre_completo", "casa__codigo")
    autocomplete_fields = ("responsable", "colonia", "casa")
    list_select_related = ("responsable", "casa__colonia", "colonia")


@admin.register(RegistroVehicular)
class RegistroVehicularAdmin(BaseAdmin):
    list_display = ("placa", "tipo_acceso", "colonia", "casa_destino", "fecha_entrada", "fecha_salida")
    list_filter = ("colonia", "tipo_acceso", "fecha_entrada", ("fecha_salida", admin.EmptyFieldListFilter))
    search_fields = ("placa", "conductor", "casa_destino__codigo")
    autocomplete_fields = ("colonia", "vehiculo", "casa_destino", "responsable_destino", "guardia_entrada", "guardia_salida")
    list_select_related = ("colonia", "casa_destino__colonia", "guardia_entrada", "guardia_salida")
    date_hierarchy = "fecha_entrada"

