from django.contrib import admin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("fecha", "usuario", "accion", "modelo", "object_id")
    list_filter = ("accion", "modelo", "fecha")
    search_fields = ("descripcion", "object_id", "usuario__username")
    readonly_fields = tuple(field.name for field in AuditLog._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
