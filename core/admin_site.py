from django.apps import apps
from django.contrib.admin import AdminSite
from django.contrib.admin.apps import AdminConfig


class PaseSeguroAdminSite(AdminSite):
    site_header = "Pase Seguro · Administración"
    site_title = "Pase Seguro"
    index_title = "Administración del sistema"
    site_url = "/dashboard/"
    index_template = "admin/paseseguro_index.html"

    def get_app_list(self, request, app_label=None):
        app_list = super().get_app_list(request, app_label)
        sections = {
            "colonias": "Residenciales y casas", "residentes": "Residentes",
            "accounts": "Usuarios y asignaciones", "facturacion": "Cuotas, pagos y comprobantes",
            "accesos": "Vehículos y accesos", "visitas": "Visitas programadas",
            "reservas": "Áreas comunes y reservas", "comunidad": "Comunidad y comunicación",
            "core": "Auditoría", "auth": "Grupos y permisos",
            "admin": "Actividad del administrador", "sessions": "Sesiones",
            "contenttypes": "Tipos de contenido",
        }
        order = {label: position for position, label in enumerate(sections)}
        labels = {
            "User": "Usuarios", "UsuarioColonia": "Asignaciones de residenciales", "Colonia": "Residenciales",
            "Casa": "Casas", "Responsable": "Residentes y responsables", "CasaResponsable": "Historial de responsables",
            "TarifaColonia": "Tarifas de vigilancia", "TarifaEspecialCasa": "Tarifas especiales por casa",
            "CuotaMensual": "Cuotas mensuales", "Pago": "Pagos y recibos", "ComprobantePago": "Comprobantes de pago",
            "ComprobanteCuota": "Períodos de comprobantes", "AplicacionPago": "Aplicaciones de pagos",
            "ReciboSecuencia": "Numeración de recibos", "CuentaPagoColonia": "Cuentas bancarias para pagos",
            "Vehiculo": "Vehículos", "RegistroVehicular": "Entradas y salidas vehiculares",
            "Visita": "Visitas programadas", "RegistroAcceso": "Accesos de visitas",
            "AreaComun": "Áreas comunes", "Reserva": "Reservas", "SolicitudMensaje": "Solicitudes y mensajes",
            "AlertaSOS": "Alertas SOS", "Comunicado": "Comunicados", "Clasificado": "Clasificados",
            "DirectorioEntrada": "Directorio", "DocumentoComunidad": "Documentos de comunidad",
            "AuditLog": "Auditoría del sistema",
        }
        for app in app_list:
            app["name"] = sections.get(app["app_label"], app["name"])
            for model in app["models"]:
                model["name"] = labels.get(model["object_name"], model["name"])
            app["models"].sort(key=lambda model: model["name"].casefold())
        return sorted(app_list, key=lambda app: order.get(app["app_label"], 99))

    def index(self, request, extra_context=None):
        cards = []
        for label, title in (("colonias.Colonia", "Residenciales"), ("colonias.Casa", "Casas"),
                             ("residentes.Responsable", "Residentes"), ("accounts.User", "Usuarios")):
            model = apps.get_model(label)
            model_admin = self._registry.get(model)
            if model_admin and model_admin.has_view_permission(request):
                from django.urls import reverse
                cards.append({"title": title, "total": model.objects.count(),
                              "url": reverse(f"admin:{model._meta.app_label}_{model._meta.model_name}_changelist")})
        return super().index(request, {**(extra_context or {}), "summary_cards": cards})


class PaseSeguroAdminConfig(AdminConfig):
    default_site = "core.admin_site.PaseSeguroAdminSite"
