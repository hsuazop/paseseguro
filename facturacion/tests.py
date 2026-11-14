from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from accounts.models import User, UsuarioColonia
from colonias.models import Casa, Colonia
from residentes.models import Responsable

from .models import ComprobanteCuota, ComprobantePago, CuotaMensual, Pago, TarifaColonia, TarifaEspecialCasa
from .services import anular_pago, generar_cuotas_mes, registrar_pago


class FinancialTestCase(TestCase):
    def setUp(self):
        self.colonia = Colonia.objects.create(nombre="Las Palmas")
        self.otra_colonia = Colonia.objects.create(nombre="El Sauce")
        self.admin = User.objects.create_user("admin", password="ClaveSegura1!", rol=User.Rol.ADMINISTRADOR)
        self.tesorero = User.objects.create_user("tesorero", password="ClaveSegura1!", rol=User.Rol.TESORERO)
        UsuarioColonia.objects.create(usuario=self.admin, colonia=self.colonia)
        UsuarioColonia.objects.create(usuario=self.tesorero, colonia=self.colonia)
        self.responsable = Responsable.objects.create(nombre_completo="Juan Perez", identidad="0801199012345")
        self.resident_user = User.objects.create_user(
            "0801199012345", identidad="0801199012345", password="ClaveSegura1!", rol=User.Rol.RESIDENTE,
        )
        self.responsable.usuario = self.resident_user
        self.responsable.save()
        self.casa = Casa.objects.create(colonia=self.colonia, codigo="001", numero="1", responsable_actual=self.responsable)
        self.otra_casa = Casa.objects.create(colonia=self.otra_colonia, codigo="001", numero="1")
        TarifaColonia.objects.create(colonia=self.colonia, monto=Decimal("500.00"), fecha_inicio=date(2026, 1, 1))

    def generar(self, mes=1):
        generar_cuotas_mes(colonia=self.colonia, anio=2026, mes=mes, usuario=self.admin)
        return CuotaMensual.objects.get(casa=self.casa, anio=2026, mes=mes)

    def pagar(self, aplicaciones, total, casa=None, responsable=None):
        return registrar_pago(
            casa=casa or self.casa,
            responsable=responsable or self.responsable,
            fecha_pago=date(2026, 1, 15),
            monto_total=Decimal(total),
            metodo_pago=Pago.Metodo.EFECTIVO,
            aplicaciones=aplicaciones,
            usuario=self.tesorero,
        )

    def test_generacion_con_tarifa_base(self):
        cuota = self.generar()
        self.assertEqual(cuota.monto_original, Decimal("500.00"))
        self.assertEqual(cuota.saldo, Decimal("500.00"))
        resultado = generar_cuotas_mes(colonia=self.colonia, anio=2026, mes=1, usuario=self.admin)
        self.assertEqual(resultado["creadas"], 0)
        self.assertEqual(resultado["existentes"], 1)

    def test_un_responsable_con_dos_residencias_recibe_una_sola_cuota(self):
        Casa.objects.create(
            colonia=self.colonia,
            codigo="001-B",
            numero="1B",
            responsable_actual=self.responsable,
        )
        resultado = generar_cuotas_mes(colonia=self.colonia, anio=2026, mes=3, usuario=self.admin)
        self.assertEqual(resultado["creadas"], 1)
        self.assertEqual(
            CuotaMensual.objects.filter(
                responsable=self.responsable,
                colonia=self.colonia,
                anio=2026,
                mes=3,
            ).count(),
            1,
        )

    def test_generacion_con_tarifa_especial_fija(self):
        TarifaEspecialCasa.objects.create(
            casa=self.casa, tipo=TarifaEspecialCasa.Tipo.MONTO_FIJO, monto=Decimal("300.00"),
            motivo="Tercera edad", fecha_inicio=date(2026, 1, 1), usuario_que_autoriza=self.admin,
        )
        self.assertEqual(self.generar().monto_original, Decimal("300.00"))

    def test_generacion_con_porcentaje(self):
        TarifaEspecialCasa.objects.create(
            casa=self.casa, tipo=TarifaEspecialCasa.Tipo.PORCENTAJE, porcentaje=Decimal("50.00"),
            motivo="Convenio", fecha_inicio=date(2026, 1, 1), usuario_que_autoriza=self.admin,
        )
        self.assertEqual(self.generar().monto_original, Decimal("250.00"))

    def test_cambio_tarifa_no_altera_historial(self):
        enero = self.generar(1)
        tarifa = TarifaColonia.objects.get(colonia=self.colonia)
        tarifa.fecha_fin = date(2026, 6, 30)
        tarifa.save()
        TarifaColonia.objects.create(colonia=self.colonia, monto=Decimal("600"), fecha_inicio=date(2026, 7, 1))
        julio = self.generar(7)
        enero.refresh_from_db()
        self.assertEqual(enero.monto_original, Decimal("500.00"))
        self.assertEqual(julio.monto_original, Decimal("600.00"))

    def test_pago_completo(self):
        cuota = self.generar()
        self.pagar([{"cuota_id": cuota.pk, "monto": "500"}], "500")
        cuota.refresh_from_db()
        self.assertEqual(cuota.estado, CuotaMensual.Estado.PAGADA)
        self.assertEqual(cuota.saldo, 0)

    def test_pago_parcial(self):
        cuota = self.generar()
        self.pagar([{"cuota_id": cuota.pk, "monto": "200"}], "200")
        cuota.refresh_from_db()
        self.assertEqual(cuota.estado, CuotaMensual.Estado.PARCIAL)
        self.assertEqual(cuota.saldo, Decimal("300.00"))

    def test_pago_cubre_dos_meses(self):
        enero, febrero = self.generar(1), self.generar(2)
        self.pagar([{"cuota_id": enero.pk, "monto": "500"}, {"cuota_id": febrero.pk, "monto": "500"}], "1000")
        enero.refresh_from_db(); febrero.refresh_from_db()
        self.assertEqual(enero.estado, CuotaMensual.Estado.PAGADA)
        self.assertEqual(febrero.estado, CuotaMensual.Estado.PAGADA)

    def test_pago_parcial_en_varios_meses(self):
        enero, febrero = self.generar(1), self.generar(2)
        self.pagar([{"cuota_id": enero.pk, "monto": "300"}, {"cuota_id": febrero.pk, "monto": "200"}], "500")
        enero.refresh_from_db(); febrero.refresh_from_db()
        self.assertEqual(enero.saldo, Decimal("200.00"))
        self.assertEqual(febrero.saldo, Decimal("300.00"))

    def test_impide_sobrepago(self):
        cuota = self.generar()
        with self.assertRaises(ValidationError):
            self.pagar([{"cuota_id": cuota.pk, "monto": "501"}], "501")
        self.assertFalse(Pago.objects.exists())

    def test_anulacion_restaura_saldo(self):
        cuota = self.generar()
        pago = self.pagar([{"cuota_id": cuota.pk, "monto": "500"}], "500")
        anular_pago(pago=pago, motivo="Registro duplicado", usuario=self.admin)
        cuota.refresh_from_db(); pago.refresh_from_db()
        self.assertTrue(pago.anulado)
        self.assertEqual(cuota.saldo, Decimal("500.00"))
        self.assertEqual(cuota.estado, CuotaMensual.Estado.PENDIENTE)

    def test_tesorero_no_accede_otra_colonia(self):
        self.client.force_login(self.tesorero)
        response = self.client.get(reverse("casa_detalle", args=(self.otra_casa.pk,)))
        self.assertEqual(response.status_code, 404)

    def test_residente_no_ve_casa_ajena(self):
        otro_responsable = Responsable.objects.create(nombre_completo="Maria", identidad="0801199011111")
        casa_ajena = Casa.objects.create(colonia=self.colonia, codigo="002", numero="2", responsable_actual=otro_responsable)
        self.client.force_login(self.resident_user)
        response = self.client.get(reverse("mi_cuenta_casa", args=(casa_ajena.pk,)))
        self.assertEqual(response.status_code, 404)

    def test_tesorero_ve_solo_sus_colonias_en_listado(self):
        self.client.force_login(self.tesorero)
        response = self.client.get(reverse("casas_lista"))
        self.assertContains(response, "Las Palmas")
        self.assertNotContains(response, "El Sauce")

    def test_tesoreria_muestra_estado_mensual_de_su_residencial(self):
        self.generar()
        self.client.force_login(self.tesorero)
        response = self.client.get(reverse("tesoreria"), {"anio": 2026, "mes": 1})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Vigilancia del mes")
        self.assertContains(response, "Juan Perez")
        self.assertContains(response, "Pendiente")
        self.assertNotContains(response, "El Sauce")

    def test_aprobar_comprobante_registra_y_aplica_el_pago(self):
        cuota = self.generar()
        comprobante = ComprobantePago.objects.create(
            casa=self.casa,
            colonia=self.colonia,
            responsable=self.responsable,
            enviado_por=self.resident_user,
            fecha_pago=date(2026, 1, 15),
            monto=Decimal("500.00"),
            metodo_pago=Pago.Metodo.TRANSFERENCIA,
            referencia="TRX-100",
            archivo=SimpleUploadedFile("comprobante.pdf", b"%PDF-1.4 prueba", content_type="application/pdf"),
        )
        ComprobanteCuota.objects.create(comprobante=comprobante, cuota=cuota)
        self.client.force_login(self.tesorero)
        response = self.client.post(reverse("comprobante_revisar", args=(comprobante.pk,)), {
            "estado": ComprobantePago.Estado.APROBADO,
            "comentario_revision": "Pago verificado.",
        })
        self.assertRedirects(response, reverse("comprobantes_gestion"))
        comprobante.refresh_from_db()
        cuota.refresh_from_db()
        self.assertEqual(comprobante.estado, ComprobantePago.Estado.APROBADO)
        self.assertIsNotNone(comprobante.pago_id)
        self.assertEqual(cuota.estado, CuotaMensual.Estado.PAGADA)

    def test_paginas_exportaciones_y_recibo_pdf(self):
        cuota = self.generar()
        pago = self.pagar([{"cuota_id": cuota.pk, "monto": "500"}], "500")
        self.client.force_login(self.admin)
        for url in (
            reverse("dashboard"), reverse("casas_lista"), reverse("casa_detalle", args=(self.casa.pk,)),
            reverse("cuotas_lista"), reverse("pagos_lista"), reverse("pago_detalle", args=(pago.pk,)),
            reverse("recibo_detalle", args=(pago.pk,)), reverse("reporte_morosidad"),
            reverse("reporte_recaudacion"), reverse("reporte_pagos"),
        ):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)
        pdf = self.client.get(reverse("recibo_pdf", args=(pago.pk,)))
        self.assertEqual(pdf.status_code, 200)
        self.assertTrue(pdf.content.startswith(b"%PDF"))
        excel = self.client.get(reverse("pagos_excel"))
        self.assertEqual(excel.status_code, 200)
        self.assertTrue(excel.content.startswith(b"PK"))

    def test_dashboard_atribuye_pago_al_mes_de_la_cuota(self):
        enero = self.generar(1)
        registrar_pago(
            casa=self.casa,
            responsable=self.responsable,
            fecha_pago=date(2026, 2, 15),
            monto_total=Decimal("500.00"),
            metodo_pago=Pago.Metodo.TRANSFERENCIA,
            aplicaciones=[{"cuota_id": enero.pk, "monto": "500.00"}],
            usuario=self.tesorero,
        )
        self.client.force_login(self.admin)
        enero_response = self.client.get(reverse("dashboard"), {
            "colonia": self.colonia.pk, "anio": 2026, "mes": 1,
        })
        febrero_response = self.client.get(reverse("dashboard"), {
            "colonia": self.colonia.pk, "anio": 2026, "mes": 2,
        })
        self.assertEqual(enero_response.context["cobrado"], Decimal("500.00"))
        self.assertEqual(len(enero_response.context["aplicaciones_mes"]), 1)
        self.assertEqual(febrero_response.context["cobrado"], Decimal("0"))
        self.assertEqual(len(febrero_response.context["aplicaciones_mes"]), 0)

    def test_dashboard_muestra_meses_en_mora_hasta_periodo_elegido(self):
        self.generar(1)
        self.generar(2)
        self.client.force_login(self.admin)
        response = self.client.get(reverse("dashboard"), {
            "colonia": self.colonia.pk, "anio": 2026, "mes": 2,
        })
        cuenta = response.context["cuentas"][0]
        self.assertEqual(cuenta["meses_mora"], 2)
        self.assertEqual(cuenta["saldo_mora"], Decimal("1000.00"))

    def test_resumen_financiero_es_una_opcion_separada(self):
        self.generar(1)
        self.client.force_login(self.admin)
        response = self.client.get(reverse("dashboard_financiero"), {
            "anio": 2026, "mes": 1,
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Resumen financiero")
        self.assertContains(response, "Las Palmas")

    def test_portal_residente_renderiza_estado_de_cuenta(self):
        self.generar()
        self.client.force_login(self.resident_user)
        response = self.client.get(reverse("mi_cuenta_casa", args=(self.casa.pk,)), {"anio": 2026})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Enero")
        self.assertContains(response, "L 500.00")

    def efectivo_datos(self, **cambios):
        datos = {
            "tipo": "existente", "casa": self.casa.pk, "mes": 1, "anio": 2026,
            "fecha_pago": "2026-02-15", "monto_total": "500.00", "observaciones": "Recibido en persona",
            "correo": "vecino@example.com",
        }
        datos.update(cambios)
        return datos

    def test_tesorero_colonia_implicita_ignora_parametros_y_sesion(self):
        self.client.force_login(self.tesorero)
        session = self.client.session
        session["colonia_actual"] = self.otra_colonia.pk
        session.save()
        response = self.client.get(reverse("tesoreria"), {"colonia": self.otra_colonia.pk, "anio": 2026})
        self.assertEqual(response.context["colonia"], self.colonia)
        self.assertContains(response, "Bienvenido, tesorero")
        self.assertNotContains(response, 'name="colonia"')
        self.assertContains(response, 'value="2026"')
        self.assertContains(response, "Nuevo vecino y pago")

    def test_formulario_efectivo_sin_selector_colonia(self):
        self.client.force_login(self.tesorero)
        response = self.client.get(reverse("pago_efectivo"), {"casa": self.casa.pk, "mes": 3, "anio": 2027})
        self.assertContains(response, "Las Palmas")
        self.assertNotContains(response, 'name="colonia"')
        self.assertNotContains(response, "El Sauce")
        self.assertEqual(response.context["form"].initial["mes"], "3")

    def test_efectivo_genera_cuota_y_recibo_sin_comprobante(self):
        self.client.force_login(self.tesorero)
        response = self.client.post(reverse("pago_efectivo"), self.efectivo_datos())
        pago = Pago.objects.get()
        self.assertRedirects(response, reverse("recibo_detalle", args=(pago.pk,)))
        cuota = CuotaMensual.objects.get(anio=2026, mes=1)
        self.assertEqual((cuota.anio, cuota.mes), (2026, 1))
        self.assertEqual(cuota.estado, CuotaMensual.Estado.PAGADA)
        self.assertEqual(pago.metodo_pago, Pago.Metodo.EFECTIVO)
        self.assertEqual(pago.usuario_que_registra, self.tesorero)
        self.assertFalse(ComprobantePago.objects.exists())
        panel = self.client.get(reverse("tesoreria"), {"anio": 2026, "mes": 1})
        self.assertEqual(panel.context["pagadas"], 1)
        self.client.post(reverse("pago_efectivo"), self.efectivo_datos())
        self.assertEqual(Pago.objects.count(), 1)

    def test_efectivo_abona_solo_al_periodo_elegido(self):
        enero = self.generar(1)
        febrero = self.generar(2)
        self.client.force_login(self.tesorero)
        self.client.post(reverse("pago_efectivo"), self.efectivo_datos(mes=2, monto_total="200"))
        enero.refresh_from_db()
        febrero.refresh_from_db()
        self.assertEqual(enero.saldo, Decimal("500"))
        self.assertEqual(febrero.saldo, Decimal("300"))

    def test_alta_vecino_y_pago_asigna_colonia_y_crea_acceso(self):
        self.client.force_login(self.tesorero)
        datos = self.efectivo_datos(tipo="nuevo", casa="", nombre_completo="Ana Lopez",
                                   identidad="0801199912345", telefono="99999999", codigo_casa="A-25")
        response = self.client.post(reverse("pago_efectivo"), datos)
        pago = Pago.objects.get()
        self.assertEqual(response.status_code, 302)
        vecino = Responsable.objects.get(identidad=datos["identidad"])
        self.assertEqual(pago.responsable, vecino)
        self.assertEqual(pago.colonia, self.colonia)
        self.assertEqual(pago.casa.responsable_actual, vecino)
        self.assertTrue(pago.casa.historial_responsables.filter(responsable=vecino, activo=True).exists())
        self.assertTrue(vecino.usuario.debe_cambiar_password)
        self.assertEqual(vecino.correo, datos["correo"])
        self.assertEqual(vecino.usuario.email, datos["correo"])
        alta = self.client.get(response.url)
        self.assertContains(alta, "Contraseña temporal")
        self.assertTrue(vecino.usuario.check_password(alta.context["alta"]["password"]))
        self.assertNotContains(self.client.get(response.url), "Contraseña temporal")

    def test_alta_fallida_revierte_vecino_casa_y_usuario(self):
        self.client.force_login(self.tesorero)
        response = self.client.post(reverse("pago_efectivo"), self.efectivo_datos(
            tipo="nuevo", nombre_completo="Ana Lopez", identidad="0801199912345", codigo_casa="A-25", monto_total="501",
        ))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Responsable.objects.filter(identidad="0801199912345").exists())
        self.assertFalse(User.objects.filter(username="0801199912345").exists())
        self.assertFalse(Casa.objects.filter(codigo="A-25").exists())
        self.assertFalse(Pago.objects.exists())

    def test_alta_usa_casa_disponible_sin_reemplazar_responsables(self):
        vacia = Casa.objects.create(colonia=self.colonia, codigo="002", numero="2")
        self.client.force_login(self.tesorero)
        datos = self.efectivo_datos(tipo="nuevo", nombre_completo="Ana Lopez", identidad="0801199912345", codigo_casa="001")
        response = self.client.post(reverse("pago_efectivo"), datos)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Pago.objects.exists())
        datos["codigo_casa"] = "002"
        self.client.post(reverse("pago_efectivo"), datos)
        self.assertEqual(Pago.objects.get().casa, vacia)

    def test_efectivo_rechaza_vecino_ajeno_y_residente_sin_permiso(self):
        self.client.force_login(self.tesorero)
        response = self.client.post(reverse("pago_efectivo"), self.efectivo_datos(casa=self.otra_casa.pk))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)
        self.assertFalse(Pago.objects.exists())
        self.client.force_login(self.resident_user)
        self.assertEqual(self.client.post(reverse("pago_efectivo"), self.efectivo_datos()).status_code, 403)

    def test_sin_tarifa_no_registra_efectivo_ni_cuota(self):
        TarifaColonia.objects.all().delete()
        self.client.force_login(self.tesorero)
        response = self.client.post(reverse("pago_efectivo"), self.efectivo_datos())
        self.assertContains(response, "no tiene una tarifa base vigente")
        self.assertFalse(Pago.objects.exists())
        self.assertFalse(CuotaMensual.objects.exists())

    def test_efectivo_exige_correo_valido_sin_crear_registros(self):
        self.client.force_login(self.tesorero)
        for correo in ("", "correo-invalido"):
            with self.subTest(correo=correo):
                response = self.client.post(reverse("pago_efectivo"), self.efectivo_datos(
                    tipo="nuevo", nombre_completo="Ana Lopez", identidad="0801199912345",
                    codigo_casa="A-25", correo=correo,
                ))
                self.assertIn("correo", response.context["form"].errors)
                self.assertFalse(Responsable.objects.filter(identidad="0801199912345").exists())
                self.assertFalse(Pago.objects.exists())

    def test_efectivo_de_vecino_existente_no_pide_ni_modifica_correo(self):
        self.responsable.correo = "juan@example.com"
        self.responsable.save()
        self.resident_user.email = "juan@example.com"
        self.resident_user.save()
        self.client.force_login(self.tesorero)
        datos = self.efectivo_datos()
        datos.pop("correo")
        response = self.client.post(reverse("pago_efectivo"), datos)
        self.assertEqual(response.status_code, 302)
        self.responsable.refresh_from_db()
        self.resident_user.refresh_from_db()
        self.assertEqual(self.responsable.correo, "juan@example.com")
        self.assertEqual(self.resident_user.email, "juan@example.com")
        response = self.client.get(reverse("pago_efectivo"), {"casa": self.casa.pk})
        self.assertFalse(response.context["form"].fields["correo"].required)
        self.assertContains(response, 'id="vecino-nuevo" class="mb-4" hidden')

    def test_pago_existente_ignora_correo_enviado_aunque_sea_invalido(self):
        self.responsable.correo = "juan@example.com"
        self.responsable.save()
        self.client.force_login(self.tesorero)
        response = self.client.post(reverse("pago_efectivo"), self.efectivo_datos(correo="correo-invalido"))
        self.assertEqual(response.status_code, 302)
        self.responsable.refresh_from_db()
        self.assertEqual(self.responsable.correo, "juan@example.com")
