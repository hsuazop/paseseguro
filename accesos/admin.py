from django.contrib import admin

from .models import RegistroVehicular, Vehiculo


@admin.register(Vehiculo)
class VehiculoAdmin(admin.ModelAdmin):
    list_display = ("placa", "responsable", "casa", "marca", "modelo", "color", "activo")
    list_filter = ("colonia", "tipo", "activo")
    search_fields = ("placa", "responsable__nombre_completo", "casa__codigo")


@admin.register(RegistroVehicular)
class RegistroVehicularAdmin(admin.ModelAdmin):
    list_display = ("placa", "tipo_acceso", "colonia", "casa_destino", "fecha_entrada", "fecha_salida")
    list_filter = ("colonia", "tipo_acceso", "fecha_entrada")
    search_fields = ("placa", "conductor", "casa_destino__codigo")

