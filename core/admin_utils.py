from django.contrib import admin


class BaseAdmin(admin.ModelAdmin):
    list_per_page = 40
    list_max_show_all = 200
    save_on_top = True
    empty_value_display = "—"
    show_full_result_count = False

    def get_readonly_fields(self, request, obj=None):
        timestamps = tuple(field.name for field in self.model._meta.fields
                           if field.name in {"created_at", "updated_at"})
        return tuple(dict.fromkeys((*super().get_readonly_fields(request, obj), *timestamps)))


class ReadOnlyAdmin(BaseAdmin):
    actions = None

    def get_readonly_fields(self, request, obj=None):
        return tuple(field.name for field in self.model._meta.fields)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
