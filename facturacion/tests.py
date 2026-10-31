from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from accounts.models import User, UsuarioColonia
from colonias.models import Casa, Colonia
from residentes.models import Responsable

from .models import CuotaMensual, Pago, TarifaColonia, TarifaEspecialCasa
from .services import anular_pago, generar_cuotas_mes, registrar_pago


class FinancialTestCase(TestCase):
    def setUp(self):
        self.colonia = Colonia.objects.create(nombre="Las Palmas")
        self.otra_colonia = Colonia.objects.create(nombre="El Sauce")
        self.admin = User.objects.create_user("admin", password="ClaveSegura1!", rol=User.Rol.ADMINISTRADOR)
        self.tesorero = User.objects.create_user("administrador2", password="ClaveSegura1!", rol=User.Rol.ADMINISTRADOR)
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

    def test_paginas_exportaciones_y_recibo_pdf(self):
        cuota = self.generar()
        pago = self.pagar([{"cuota_id": cuota.pk, "monto": "500"}], "500")
        self.client.force_login(self.tesorero)
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
        self.client.force_login(self.tesorero)
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
        self.client.force_login(self.tesorero)
        response = self.client.get(reverse("dashboard"), {
            "colonia": self.colonia.pk, "anio": 2026, "mes": 2,
        })
        cuenta = response.context["cuentas"][0]
        self.assertEqual(cuenta["meses_mora"], 2)
        self.assertEqual(cuenta["saldo_mora"], Decimal("1000.00"))

    def test_resumen_financiero_es_una_opcion_separada(self):
        self.generar(1)
        self.client.force_login(self.tesorero)
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
