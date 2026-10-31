"""
URL configuration for myproject project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.contrib.auth.views import LogoutView
from django.conf import settings
from django.conf.urls.static import static
from django.urls import include, path

from accounts import views as account_views
from colonias import views as colonia_views
from core import views as core_views
from facturacion import views as factura_views
from reportes import views as reporte_views
from residentes import views as residente_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('login/', account_views.AccesoView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('cambiar-password/', account_views.cambiar_password_obligatorio, name='cambiar_password_obligatorio'),
    path('', core_views.dashboard, name='inicio'),
    path('dashboard/', core_views.dashboard, name='dashboard'),
    path('dashboard/financiero/', core_views.dashboard_financiero, name='dashboard_financiero'),
    path('usuarios/', account_views.usuarios_lista, name='usuarios_lista'),
    path('usuarios/nuevo/', account_views.usuario_crear, name='usuario_crear'),
    path('usuarios/<int:pk>/restablecer-password/', account_views.usuario_reset_password, name='usuario_reset_password'),
    path('colonias/', colonia_views.colonias_lista, name='colonias_lista'),
    path('colonias/nueva/', colonia_views.colonia_crear, name='colonia_crear'),
    path('colonias/<int:pk>/', colonia_views.colonia_detalle, name='colonia_detalle'),
    path('colonias/<int:pk>/editar/', colonia_views.colonia_editar, name='colonia_editar'),
    path('casas/', colonia_views.casas_lista, name='casas_lista'),
    path('casas/nueva/', colonia_views.casa_crear, name='casa_crear'),
    path('casas/importar/', colonia_views.importar_casas, name='importar_casas'),
    path('casas/<int:pk>/', colonia_views.casa_detalle, name='casa_detalle'),
    path('casas/<int:pk>/editar/', colonia_views.casa_editar, name='casa_editar'),
    path('casas/<int:pk>/responsable/', colonia_views.casa_asignar_responsable, name='casa_asignar_responsable'),
    path('responsables/', residente_views.responsables_lista, name='responsables_lista'),
    path('responsables/nuevo/', residente_views.responsable_crear, name='responsable_crear'),
    path('responsables/<int:pk>/', residente_views.responsable_detalle, name='responsable_detalle'),
    path('tarifas/', factura_views.tarifas_lista, name='tarifas_lista'),
    path('tarifas/nueva/', factura_views.tarifa_crear, name='tarifa_crear'),
    path('tarifas/especial/nueva/', factura_views.tarifa_especial_crear, name='tarifa_especial_crear'),
    path('tarifas/cuentas-pago/nueva/', factura_views.cuenta_pago_crear, name='cuenta_pago_crear'),
    path('cuotas/', factura_views.cuotas_lista, name='cuotas_lista'),
    path('cuotas/generar/', factura_views.cuotas_generar, name='cuotas_generar'),
    path('pagos/', factura_views.pagos_lista, name='pagos_lista'),
    path('pagos/nuevo/', factura_views.pago_nuevo, name='pago_nuevo'),
    path('pagos/<int:pk>/', factura_views.pago_detalle, name='pago_detalle'),
    path('pagos/<int:pk>/anular/', factura_views.pago_anular, name='pago_anular'),
    path('recibos/<int:pk>/', factura_views.recibo_detalle, name='recibo_detalle'),
    path('recibos/<int:pk>/pdf/', factura_views.recibo_pdf, name='recibo_pdf'),
    path('recibos/publico/<uuid:token>/', factura_views.recibo_publico, name='recibo_publico'),
    path('recibos/publico/<uuid:token>/pdf/', factura_views.recibo_publico_pdf, name='recibo_publico_pdf'),
    path('mi-cuenta/<int:casa_id>/comprobantes/', factura_views.comprobantes_residente, name='comprobantes_residente'),
    path('mi-cuenta/<int:casa_id>/comprobantes/enviar/', factura_views.comprobante_enviar, name='comprobante_enviar'),
    path('mi-cuenta/<int:casa_id>/cuentas-pago/', factura_views.cuenta_pago_residente, name='cuenta_pago_residente'),
    path('comprobantes/', factura_views.comprobantes_gestion, name='comprobantes_gestion'),
    path('comprobantes/<int:pk>/revisar/', factura_views.comprobante_revisar, name='comprobante_revisar'),
    path('reportes/morosidad/', reporte_views.morosidad, name='reporte_morosidad'),
    path('reportes/morosidad/excel/', reporte_views.exportar_morosidad_excel, name='morosidad_excel'),
    path('reportes/recaudacion/', reporte_views.recaudacion, name='reporte_recaudacion'),
    path('reportes/recaudacion/excel/', reporte_views.exportar_recaudacion_excel, name='recaudacion_excel'),
    path('reportes/pagos/', reporte_views.historial_pagos, name='reporte_pagos'),
    path('reportes/pagos/excel/', reporte_views.exportar_pagos_excel, name='pagos_excel'),
    path('reportes/<str:tipo>/pdf/', reporte_views.reporte_pdf, name='reporte_pdf'),
    path('mi-cuenta/', residente_views.mi_cuenta, name='mi_cuenta'),
    path('mi-cuenta/<int:casa_id>/', residente_views.mi_cuenta_casa, name='mi_cuenta_casa'),
    path('mi-cuenta/<int:casa_id>/inicio/', residente_views.portal_residente, name='portal_residente'),
    path('mi-cuenta/<int:casa_id>/configuracion/', residente_views.configurar_perfil, name='configurar_perfil'),
    path('', include('visitas.urls')),
    path('', include('comunidad.urls')),
    path('', include('reservas.urls')),
    path('', include('accesos.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
