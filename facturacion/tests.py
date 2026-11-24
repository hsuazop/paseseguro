from datetime import date
from decimal import Decimal
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core import mail
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from accesos.models import Vehiculo
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

    def test_tesoreria_suma_solo_aplicaciones_del_periodo_sin_duplicar_casas(self):
        enero, febrero = self.generar(1), self.generar(2)
        Casa.objects.create(colonia=self.colonia, codigo="001-B", responsable_actual=self.responsable)
        pago = self.pagar([
            {"cuota_id": enero.pk, "monto": "500"},
            {"cuota_id": febrero.pk, "monto": "200"},
        ], "700")
        self.client.force_login(self.tesorero)
        for mes, cobrado, saldo, porcentaje in ((1, "500", "0", "100"), (2, "200", "300", "40")):
            with self.subTest(mes=mes):
                response = self.client.get(reverse("tesoreria"), {"anio": 2026, "mes": mes})
                self.assertEqual(response.context["esperado"], Decimal("500"))
                self.assertEqual(response.context["recaudado"], Decimal(cobrado))
                self.assertEqual(response.context["saldo_periodo"], Decimal(saldo))
                self.assertEqual(response.context["porcentaje"], Decimal(porcentaje))
                self.assertEqual(len(response.context["aplicaciones"]), 1)
                self.assertContains(response, reverse("recibo_detalle", args=[pago.pk]))
        anular_pago(pago=pago, motivo="Prueba de anulación", usuario=self.admin)
        response = self.client.get(reverse("tesoreria"), {"anio": 2026, "mes": 2})
        self.assertEqual(response.context["recaudado"], 0)
        self.assertEqual(response.context["saldo_periodo"], 500)
        self.assertEqual(len(response.context["aplicaciones"]), 0)

    def test_resumen_tesoreria_aisla_colonia_y_anio(self):
        cuota = self.generar(1)
        self.pagar([{"cuota_id": cuota.pk, "monto": "500"}], "500")
        self.client.force_login(self.tesorero)
        response = self.client.get(reverse("tesoreria"), {"anio": 2025, "mes": 1})
        self.assertEqual(response.context["esperado"], 0)
        self.assertEqual(response.context["recaudado"], 0)
        self.assertEqual(response.context["porcentaje"], 0)
        otro = Responsable.objects.create(nombre_completo="Vecino ajeno", identidad="999")
        cuota_ajena = CuotaMensual.objects.create(casa=self.otra_casa, colonia=self.otra_colonia,
            responsable=otro, anio=2026, mes=1, monto_original=900, saldo=900)
        pago_ajeno = self.pagar([{"cuota_id": cuota_ajena.pk, "monto": "900"}], "900",
            casa=self.otra_casa, responsable=otro)
        response = self.client.get(reverse("tesoreria"), {"anio": 2026, "mes": 1, "colonia": self.otra_colonia.pk})
        self.assertEqual(response.context["recaudado"], 500)
        self.assertEqual(response.context["esperado"], 500)
        self.assertNotContains(response, reverse("recibo_detalle", args=[pago_ajeno.pk]))
        self.assertNotContains(response, "Vecino ajeno")

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
        self.assertContains(response, reverse("registrar_residente"))

    def test_formulario_efectivo_sin_selector_colonia(self):
        self.client.force_login(self.tesorero)
        response = self.client.get(reverse("pago_efectivo"), {"casa": self.casa.pk, "mes": 3, "anio": 2027})
        self.assertContains(response, "Las Palmas")
        self.assertNotContains(response, 'name="colonia"')
        self.assertNotContains(response, "El Sauce")
        self.assertEqual(response.context["form"].initial["mes"], "3")

    def test_comprobante_tesoreria_abonos_y_canales_por_periodo(self):
        self.client.force_login(self.tesorero)
        url = reverse("comprobante_tesoreria")
        operacion = self.client.get(url).context["form"]["operacion"].value()
        datos = self.efectivo_datos(monto_total="100.00", metodo_pago="DEPOSITO", operacion=operacion)
        def subir(**campos):
            archivo = SimpleUploadedFile("deposito.pdf", b"%PDF-1.4 prueba", content_type="application/pdf")
            return self.client.post(url, {**datos, **campos, "archivo": archivo})

        with TemporaryDirectory() as carpeta, self.settings(MEDIA_ROOT=carpeta):
            self.assertIn("casa", subir(casa=self.otra_casa.pk).context["form"].errors)
            self.assertIn("500", str(subir(monto_total="700").context["form"].non_field_errors()))
            self.assertFalse(Pago.objects.exists())
            pago_response = subir(banco="BAC", numero_cuenta="001", referencia="0004-A")
            item = ComprobantePago.objects.get()
            self.assertRedirects(pago_response, reverse("recibo_detalle", args=[item.pago_id]))
            self.assertEqual(item.enviado_por, self.tesorero)
            self.assertEqual(item.responsable, self.responsable)
            self.assertEqual(item.banco, "BAC")
            self.assertEqual(item.referencia, "0004-A")
            self.assertEqual(item.pago.referencia, "0004-A")
            self.assertEqual(item.pago.metodo_pago, Pago.Metodo.DEPOSITO)
            self.tesorero.email = "tesorero@example.com"
            self.tesorero.save()
            self.assertNotEqual(item.correo_residente, self.tesorero.email)
            self.assertEqual(subir().status_code, 302)
            self.assertEqual(Pago.objects.count(), 1)
            self.client.post(reverse("pago_efectivo"), self.efectivo_datos(monto_total="100"))
            cuota = item.cuotas.get()
            comprobante_app = ComprobantePago.objects.create(
                casa=self.casa, colonia=self.colonia, responsable=self.responsable, enviado_por=self.resident_user,
                monto=300, metodo_pago="TRANSFERENCIA", archivo="comprobantes/prueba.pdf",
            )
            ComprobanteCuota.objects.create(comprobante=comprobante_app, cuota=cuota)
            duplicado = self.client.post(reverse("comprobante_revisar", args=[comprobante_app.pk]), {
                "estado": "APROBADO", "anio": 2026, "mes": 2, "referencia": "0004-a",
            })
            self.assertContains(duplicado, "referencia bancaria ya se usó")
            comprobante_app.refresh_from_db()
            self.assertIsNone(comprobante_app.pago_id)
            self.assertEqual(comprobante_app.cuotas.get(), cuota)
            self.client.post(reverse("comprobante_revisar", args=[comprobante_app.pk]), {"estado": "APROBADO"})
            filas = self.client.get(reverse("tesoreria"), {"mes": 1, "anio": 2026}).context["filas"]
            fila = next(f for f in filas if f["casa"] == self.casa)
            self.assertEqual(set(fila["canales"]), {"Comprobante subido por Tesorería", "Efectivo", "App"})
            self.assertEqual(fila["estado"], "PAGADA")
            self.client.force_login(self.resident_user)
            self.assertEqual(self.client.get(url).status_code, 403)
            historial = self.client.get(reverse("comprobantes_residente", args=[self.casa.pk]))
            self.assertIn(item, historial.context["comprobantes"])

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

    def datos_residente(self, **cambios):
        datos = {"nombre_completo": "Ana Lopez", "identidad": "0801199912345",
                 "telefono": "99999999", "correo": "ana@example.com", "codigo_casa": "A-25"}
        return {**datos, **cambios}

    def test_alta_independiente_y_cobro_posterior(self):
        self.client.force_login(self.tesorero)
        url = reverse("registrar_residente")
        descripcion = "Villa Olímpica, bloque B, casa 12, frente a la cancha de fútbol y junto al portón azul."
        datos = self.datos_residente(codigo_casa=descripcion.replace(", frente", ",\r\nfrente"), etapa_sector="3")
        form = self.client.get(url).context["form"]
        self.assertNotIn("monto_total", form.fields)
        self.assertNotIn("fecha_pago", form.fields)
        response = self.client.post(url, datos)
        self.assertFalse(Pago.objects.exists())
        vecino = Responsable.objects.get(identidad=datos["identidad"])
        self.assertEqual(vecino.etapa_sector, 3)
        self.assertContains(self.client.get(reverse("tesoreria_residentes")), "Etapa o sector 3")
        casa = Casa.objects.get(colonia=self.colonia, codigo=descripcion)
        self.assertEqual(casa.numero, descripcion)
        self.assertRedirects(response, f"{url}?alta={casa.pk}", fetch_redirect_response=False)
        self.assertEqual(casa.responsable_actual, vecino)
        self.assertTrue(casa.historial_responsables.filter(responsable=vecino, activo=True).exists())
        self.assertTrue(vecino.usuario.debe_cambiar_password)
        self.assertEqual(vecino.correo, datos["correo"])
        self.assertEqual(vecino.usuario.email, datos["correo"])
        alta = self.client.get(response.url)
        self.assertTrue(vecino.usuario.check_password(alta.context["alta"]["password"]))
        self.assertContains(alta, "Se enviaron las credenciales")
        self.assertContains(alta, vecino.correo)
        mensaje, = mail.outbox
        self.assertEqual(mensaje.to, [vecino.correo])
        self.assertIn(f"Usuario: {vecino.usuario.username}\n", mensaje.body)
        self.assertIn(f"Contraseña temporal: {alta.context['alta']['password']}\n", mensaje.body)
        self.assertIn(reverse("login"), mensaje.body)
        self.assertNotContains(self.client.get(response.url), "Contraseña temporal")
        self.assertEqual(len(mail.outbox), 1)
        self.assertContains(alta, f'{reverse("pago_efectivo")}?casa={casa.pk}')
        self.client.post(reverse("pago_efectivo"), self.efectivo_datos(casa=casa.pk))
        self.assertEqual(Pago.objects.get().responsable, vecino)

    @patch("residentes.services.send_mail", side_effect=OSError)
    def test_alta_con_fallo_de_correo_conserva_credenciales(self, enviar):
        self.client.force_login(self.tesorero)
        datos = self.datos_residente(identidad="")
        respuesta = self.client.post(reverse("registrar_residente"), datos, follow=True)
        self.assertContains(respuesta, "falló el envío")
        usuario = Casa.objects.get(colonia=self.colonia, codigo=datos["codigo_casa"]).responsable_actual.usuario
        self.assertContains(respuesta, usuario.username)
        clave = respuesta.context["alta"]["password"]
        self.assertContains(respuesta, clave)
        self.assertTrue(usuario.check_password(clave))
        enviar.assert_called_once()

    def test_efectivo_no_admite_alta_desde_formulario_anterior(self):
        self.client.force_login(self.tesorero)
        url = reverse("pago_efectivo")
        self.assertRedirects(self.client.get(url, {"tipo": "nuevo"}), reverse("registrar_residente"))
        datos = {**self.efectivo_datos(tipo="nuevo"), **self.datos_residente()}
        response = self.client.post(url, datos)
        self.assertContains(response, "Use Registrar Residente")
        self.assertFalse(Responsable.objects.filter(identidad=datos["identidad"]).exists())
        self.assertFalse(User.objects.filter(username=datos["identidad"]).exists())
        self.assertFalse(Casa.objects.filter(codigo=datos["codigo_casa"]).exists())
        self.assertFalse(Pago.objects.exists())

    def test_alta_usa_casa_disponible_sin_reemplazar_responsables(self):
        vacia = Casa.objects.create(colonia=self.colonia, codigo="002", numero="2")
        self.client.force_login(self.tesorero)
        url = reverse("registrar_residente")
        response = self.client.post(url, self.datos_residente(codigo_casa="001"))
        self.assertIn("codigo_casa", response.context["form"].errors)
        self.client.post(url, self.datos_residente(codigo_casa="002", colonia=self.otra_colonia.pk))
        vacia.refresh_from_db()
        self.assertEqual(vacia.responsable_actual.identidad, self.datos_residente()["identidad"])
        self.assertFalse(Pago.objects.exists())
        self.client.force_login(self.resident_user)
        self.assertEqual(self.client.post(url, self.datos_residente()).status_code, 403)

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

    def test_alta_solo_requiere_nombre_y_descripcion(self):
        self.client.force_login(self.tesorero)
        url = reverse("registrar_residente")
        self.assertEqual(set(self.client.post(url, {}).context["form"].errors), {"nombre_completo", "codigo_casa"})
        usuarios = set()
        for casa in ("A-25", "A-26"):
            alta = self.client.post(url, {"nombre_completo": "Ana Lopez", "codigo_casa": casa}, follow=True)
            vecino = Casa.objects.get(colonia=self.colonia, codigo=casa).responsable_actual
            self.assertIsNone(vecino.identidad)
            self.assertEqual(vecino.etapa_sector, 1)
            self.assertIsNone(vecino.usuario.identidad)
            self.assertEqual((vecino.telefono, vecino.correo), ("", ""))
            self.assertContains(alta, vecino.usuario.username)
            self.assertTrue(vecino.usuario.check_password(alta.context["alta"]["password"]))
            usuarios.add(vecino.usuario.username)
        self.assertEqual(len(usuarios), 2)
        self.assertEqual(len(mail.outbox), 0)

    def test_alta_rechaza_correo_invalido_si_se_indica(self):
        self.client.force_login(self.tesorero)
        response = self.client.post(reverse("registrar_residente"), self.datos_residente(correo="correo-invalido"))
        self.assertIn("correo", response.context["form"].errors)
        self.assertFalse(Responsable.objects.filter(identidad="0801199912345").exists())

    def test_alta_con_vehiculo_y_placa_duplicada(self):
        self.client.force_login(self.tesorero)
        url = reverse("registrar_residente")
        datos = {
            "nombre_completo": "Ana Lopez", "codigo_casa": "A-25",
            "agregar_vehiculo": "1", "vehiculo-placa": "haa 1234",
            "vehiculo-tipo": Vehiculo.Tipo.PICKUP, "vehiculo-color": "Azul",
        }
        alta = self.client.post(url, datos, follow=True)
        self.assertContains(alta, "HAA1234")
        vehiculo = Vehiculo.objects.get(placa="HAA1234")
        self.assertEqual(vehiculo.casa.codigo, "A-25")
        self.assertEqual(vehiculo.responsable, vehiculo.casa.responsable_actual)
        self.assertEqual(vehiculo.colonia, self.colonia)
        self.assertEqual(vehiculo.color, "Azul")
        cuentas = User.objects.count()
        datos.update(nombre_completo="Luis Perez", codigo_casa="A-26")
        repetido = self.client.post(url, datos)
        self.assertTrue(repetido.context["form"].non_field_errors())
        self.assertFalse(Casa.objects.filter(codigo="A-26").exists())
        self.assertFalse(Responsable.objects.filter(nombre_completo="Luis Perez").exists())
        self.assertEqual(User.objects.count(), cuentas)
        datos["vehiculo-placa"] = ""
        incompleto = self.client.post(url, datos)
        self.assertIn("placa", incompleto.context["form_vehiculo"].errors)
        self.assertTrue(incompleto.context["agregar_vehiculo"])
        datos.pop("agregar_vehiculo")
        self.assertEqual(self.client.post(url, datos).status_code, 302)
        self.assertEqual(Vehiculo.objects.count(), 1)

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
        self.assertNotIn("correo", response.context["form"].fields)
        self.assertNotContains(response, 'name="tipo"')

    def test_pago_existente_ignora_correo_enviado_aunque_sea_invalido(self):
        self.responsable.correo = "juan@example.com"
        self.responsable.save()
        self.client.force_login(self.tesorero)
        response = self.client.post(reverse("pago_efectivo"), self.efectivo_datos(correo="correo-invalido"))
        self.assertEqual(response.status_code, 302)
        self.responsable.refresh_from_db()
        self.assertEqual(self.responsable.correo, "juan@example.com")
