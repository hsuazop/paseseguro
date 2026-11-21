from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from core.admin_utils import BaseAdmin

from .models import User, UsuarioColonia


class UsuarioColoniaInline(admin.TabularInline):
    model = UsuarioColonia
    extra = 0
    autocomplete_fields = ("colonia",)


@admin.register(User)
class CustomUserAdmin(UserAdmin, BaseAdmin):
    fieldsets = UserAdmin.fieldsets + (("Residencia Segura", {"fields": ("identidad", "rol", "debe_cambiar_password")}),)
    add_fieldsets = UserAdmin.add_fieldsets + (("Residencia Segura", {"fields": ("identidad", "rol")}),)
    list_display = ("username", "nombre_completo", "email", "identidad", "rol", "is_staff", "is_superuser", "is_active", "last_login")
    list_filter = UserAdmin.list_filter + ("rol",)
    search_fields = ("username", "first_name", "last_name", "email", "identidad")
    inlines = (UsuarioColoniaInline,)
    date_hierarchy = "date_joined"


@admin.register(UsuarioColonia)
class UsuarioColoniaAdmin(BaseAdmin):
    list_display = ("usuario", "colonia", "activa")
    list_filter = ("activa", "colonia")
    search_fields = ("usuario__username", "usuario__first_name", "usuario__last_name", "colonia__nombre")
    autocomplete_fields = ("usuario", "colonia")
    list_select_related = ("usuario", "colonia")
