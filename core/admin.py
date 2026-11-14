from django.contrib import admin
from django.contrib.admin.models import LogEntry
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.contrib.sessions.models import Session
from .admin_utils import BaseAdmin, ReadOnlyAdmin

from .models import AuditLog


@admin.register(AuditLog)
class AuditLogAdmin(ReadOnlyAdmin):
    list_display = ("fecha", "usuario", "accion", "modelo", "object_id")
    list_filter = ("accion", "modelo", "fecha")
    search_fields = ("descripcion", "object_id", "usuario__username")
    readonly_fields = tuple(field.name for field in AuditLog._meta.fields)
    date_hierarchy = "fecha"
    list_select_related = ("usuario",)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Permission)
class PermissionAdmin(BaseAdmin):
    list_display = ("name", "codename", "content_type")
    list_filter = ("content_type__app_label",)
    search_fields = ("name", "codename", "content_type__app_label", "content_type__model")
    autocomplete_fields = ("content_type",)
    list_select_related = ("content_type",)


@admin.register(ContentType)
class ContentTypeAdmin(ReadOnlyAdmin):
    list_display = ("app_label", "model")
    list_filter = ("app_label",)
    search_fields = ("app_label", "model")


@admin.register(Session)
class SessionAdmin(ReadOnlyAdmin):
    list_display = ("session_key", "expire_date")
    list_filter = ("expire_date",)
    search_fields = ("=session_key",)
    date_hierarchy = "expire_date"
    fields = ("session_key", "expire_date")

    def has_delete_permission(self, request, obj=None):
        return admin.ModelAdmin.has_delete_permission(self, request, obj)


@admin.register(LogEntry)
class LogEntryAdmin(ReadOnlyAdmin):
    list_display = ("action_time", "user", "content_type", "object_repr", "action_flag")
    list_filter = ("action_flag", "content_type", "action_time")
    search_fields = ("object_repr", "object_id", "user__username", "change_message")
    date_hierarchy = "action_time"
    list_select_related = ("user", "content_type")
