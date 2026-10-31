from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User, UsuarioColonia


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (("Pase Seguro", {"fields": ("identidad", "rol", "debe_cambiar_password")}),)
    add_fieldsets = UserAdmin.add_fieldsets + (("Pase Seguro", {"fields": ("identidad", "rol")}),)
    list_display = ("username", "first_name", "last_name", "identidad", "rol", "is_active")
    list_filter = UserAdmin.list_filter + ("rol",)


@admin.register(UsuarioColonia)
class UsuarioColoniaAdmin(admin.ModelAdmin):
    list_display = ("usuario", "colonia", "activa")
    list_filter = ("activa", "colonia")
