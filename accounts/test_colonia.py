from datetime import date
from io import BytesIO

from django.test import TestCase
from django.urls import reverse
from openpyxl import load_workbook

from accesos.models import RegistroVehicular
from colonias.models import Casa, Colonia
from comunidad.models import Comunicado, DirectorioEntrada
from facturacion.models import CuotaMensual
from residentes.models import Responsable
from reservas.models import AreaComun
from .models import User, UsuarioColonia
from .permissions import colonias_permitidas


class ColoniaImplicitaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.colonia = Colonia.objects.create(nombre="Residencial Propia")
        cls.otra = Colonia.objects.create(nombre="Residencial Ajena")
        cls.tesorero = User.objects.create_user("tesorero", rol=User.Rol.TESORERO)
        cls.guardia = User.objects.create_user("guardia", rol=User.Rol.GUARDIA)
        cls.admin = User.objects.create_user("admin", rol=User.Rol.ADMINISTRADOR)
        cls.residente = User.objects.create_user("residente", rol=User.Rol.RESIDENTE)
        for user in (cls.tesorero, cls.guardia, cls.admin):
            UsuarioColonia.objects.create(usuario=user, colonia=cls.colonia)
        UsuarioColonia.objects.create(usuario=cls.admin, colonia=cls.otra)
        responsable = Responsable.objects.create(nombre_completo="Vecino Propio", identidad="001", usuario=cls.residente)
        ajeno = Responsable.objects.create(nombre_completo="Vecino Ajeno", identidad="002")
        cls.casa = Casa.objects.create(colonia=cls.colonia, codigo="1", numero="1", responsable_actual=responsable)
        cls.casa_ajena = Casa.objects.create(colonia=cls.otra, codigo="2", numero="2", responsable_actual=ajeno)
        for casa in (cls.casa, cls.casa_ajena):
            CuotaMensual.objects.create(casa=casa, responsable=casa.responsable_actual, colonia=casa.colonia,
                                       anio=2026, mes=1, monto_original=500, saldo=500)

    def comprobar_pantallas(self, user, nombres, kwargs=None):
        self.client.force_login(user)
        for nombre in nombres:
            with self.subTest(rol=user.rol, pantalla=nombre):
                response = self.client.get(reverse(nombre, kwargs=kwargs), {"colonia": self.otra.pk})
                self.assertEqual(response.status_code, 200)
                self.assertNotRegex(response.content.decode(), r'<(?:select|input)\b[^>]*\bname=[\"\x27]colonia[\"\x27]')
                self.assertNotContains(response, "Todas las colonias")
                if response.context and "form" in response.context:
                    self.assertNotIn("colonia", response.context["form"].fields)

    def test_todas_las_pantallas_del_tesorero_sin_selector(self):
        self.comprobar_pantallas(self.tesorero, (
            "tesoreria", "pago_efectivo", "pagos_lista", "pago_nuevo", "cuotas_lista", "casas_lista",
            "comprobantes_gestion", "reporte_morosidad", "reporte_recaudacion", "reporte_pagos",
            "bandeja_comunidad", "comunicado_crear", "directorio_crear", "documento_crear",
            "reservas_gestion", "area_crear",
        ))

    def test_todas_las_pantallas_del_guardia_sin_selector(self):
        self.comprobar_pantallas(self.guardia, (
            "dashboard_guardia", "registrar_entrada", "historial_accesos", "visitas_control",
        ))

    def test_pantallas_del_residente_sin_selector(self):
        self.comprobar_pantallas(self.residente, (
            "portal_residente", "mi_cuenta_casa", "configurar_perfil", "comprobantes_residente",
            "comprobante_enviar", "cuenta_pago_residente", "solicitudes_lista", "solicitud_crear",
            "comunidad_muro", "alerta_sos", "comunicados_lista", "clasificados_lista", "clasificado_crear",
            "directorio_documentos", "areas_lista", "reserva_crear", "mis_vehiculos", "vehiculo_crear",
            "visitas_lista", "visita_crear", "qr_residente",
        ), kwargs={"casa_id": self.casa.pk})

    def test_administrador_conserva_selector_para_gestionar(self):
        self.client.force_login(self.admin)
        for nombre in ("reporte_morosidad", "reporte_recaudacion", "cuotas_lista", "dashboard_guardia", "area_crear"):
            with self.subTest(pantalla=nombre):
                response = self.client.get(reverse(nombre))
                self.assertContains(response, 'name="colonia"')

    def test_guardia_ignora_colonia_en_get_post_y_sesion(self):
        self.client.force_login(self.guardia)
        sesion = self.client.session
        sesion["colonia_actual"] = self.otra.pk
        sesion.save()
        response = self.client.get(reverse("dashboard_guardia"), {"colonia": "valor-invalido"})
        self.assertEqual(response.context["colonia"], self.colonia)
        response = self.client.post(reverse("registrar_entrada"), {
            "colonia": self.otra.pk, "placa": "HAA1234", "personas": 1,
            "tipo_acceso": RegistroVehicular.TipoAcceso.VISITANTE,
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(RegistroVehicular.objects.get().colonia, self.colonia)

    def test_reportes_y_exportaciones_usan_colonia_asignada(self):
        self.client.force_login(self.tesorero)
        response = self.client.get(reverse("reporte_morosidad"), {"colonia": self.otra.pk})
        self.assertContains(response, "Vecino Propio")
        self.assertNotContains(response, "Vecino Ajeno")
        for nombre in ("reporte_recaudacion", "cuotas_lista", "casas_lista"):
            response = self.client.get(reverse(nombre), {"colonia": self.otra.pk})
            self.assertContains(response, "Residencial Propia")
            self.assertNotContains(response, "Residencial Ajena")
        for nombre in ("morosidad_excel", "recaudacion_excel"):
            response = self.client.get(reverse(nombre), {"colonia": self.otra.pk})
            libro = load_workbook(BytesIO(response.content), read_only=True)
            filas = list(libro.active.values)
            libro.close()
            self.assertTrue(any("Residencial Propia" in fila for fila in filas))
            self.assertFalse(any("Residencial Ajena" in fila for fila in filas))

    def test_catalogos_se_guardan_en_su_colonia_sin_campo(self):
        self.client.force_login(self.tesorero)
        casos = (
            ("comunicado_crear", Comunicado, {"titulo": "Aviso", "contenido": "Aviso a vecinos", "activo": "on"}),
            ("directorio_crear", DirectorioEntrada, {"nombre": "Contacto", "telefono": "99999999", "activo": "on"}),
            ("area_crear", AreaComun, {"nombre": "Salón", "capacidad": 20, "costo": "0", "activa": "on"}),
        )
        for nombre, modelo, datos in casos:
            with self.subTest(pantalla=nombre):
                response = self.client.post(reverse(nombre), {**datos, "colonia": self.otra.pk})
                self.assertEqual(response.status_code, 302)
                self.assertEqual(modelo.objects.get().colonia, self.colonia)

    def test_sin_asignacion_no_se_usa_colonia_de_la_peticion(self):
        UsuarioColonia.objects.filter(usuario=self.tesorero).delete()
        self.client.force_login(self.tesorero)
        response = self.client.get(reverse("reporte_morosidad"), {"colonia": self.colonia.pk})
        self.assertNotContains(response, "Vecino Propio")
        self.assertNotContains(response, 'name="colonia"')
        self.assertContains(response, "Sin residencial activa asignada")
        self.assertEqual(self.client.get(reverse("area_crear")).status_code, 403)

    def test_perfil_operativo_no_cambia_de_colonia_con_asignaciones_antiguas(self):
        UsuarioColonia.objects.create(usuario=self.tesorero, colonia=self.otra)
        self.assertEqual(list(colonias_permitidas(self.tesorero)), [self.colonia])
        self.client.force_login(self.tesorero)
        self.assertEqual(self.client.get(reverse("casa_detalle", args=(self.casa_ajena.pk,))).status_code, 404)
