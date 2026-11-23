from datetime import date, datetime, timezone as datetime_timezone
from decimal import Decimal
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from colonias.models import Casa, Colonia
from facturacion.models import ComprobantePago, CuotaMensual
from residentes.models import Responsable


class ComprobantePortalTests(TestCase):
    def setUp(self):
        self.media = TemporaryDirectory()
        self.addCleanup(self.media.cleanup)
        media_settings = override_settings(MEDIA_ROOT=self.media.name)
        media_settings.enable()
        self.addCleanup(media_settings.disable)
        self.colonia = Colonia.objects.create(nombre="Colonia Comprobantes")
        self.usuario = User.objects.create_user(
            username="0303000000001",
            identidad="0303000000001",
            password="Clave2026!",
            rol=User.Rol.RESIDENTE,
        )
        self.responsable = Responsable.objects.create(
            nombre_completo="Residente Comprobante",
            identidad="0303000000001",
            usuario=self.usuario,
        )
        self.casa = Casa.objects.create(
            colonia=self.colonia,
            codigo="P1",
            numero="1",
            responsable_actual=self.responsable,
        )
        self.cuota = CuotaMensual.objects.create(
            casa=self.casa,
            responsable=self.responsable,
            colonia=self.colonia,
            anio=2026,
            mes=10,
            monto_original=Decimal("500.00"),
            monto_pagado=Decimal("0.00"),
            saldo=Decimal("500.00"),
        )

    def test_envio_comprobante_no_modifica_saldo_financiero(self):
        self.client.force_login(self.usuario)
        self.responsable.banco = "BAC"
        self.responsable.numero_cuenta = "009100"
        self.responsable.save()
        form = self.client.get(reverse("comprobante_enviar", args=(self.casa.pk,))).context["form"]
        self.assertEqual((form["banco"].value(), form["numero_cuenta"].value()), ("BAC", "009100"))
        archivo = SimpleUploadedFile("comprobante.pdf", b"contenido-de-prueba", content_type="application/pdf")
        response = self.client.post(
            reverse("comprobante_enviar", kwargs={"casa_id": self.casa.pk}),
            {
                "anio": 2026,
                "mes": 10,
                "monto": "500.00",
                "metodo_pago": "TRANSFERENCIA",
                "referencia": "ABC123",
                "banco": "FICOHSA",
                "numero_cuenta": "000001",
                "archivo": archivo,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(ComprobantePago.objects.count(), 1)
        comprobante = ComprobantePago.objects.get()
        self.assertEqual((comprobante.banco, comprobante.numero_cuenta), ("FICOHSA", "000001"))
        self.cuota.refresh_from_db()
        self.assertEqual(self.cuota.saldo, Decimal("500.00"))
        self.assertEqual(self.cuota.monto_pagado, Decimal("0.00"))

    def enviar(self, **cambios):
        self.client.force_login(self.usuario)
        datos = {
            "anio": 2026, "mes": 10, "monto": "500.00",
            "metodo_pago": "TRANSFERENCIA", "referencia": "ABC123",
            "archivo": SimpleUploadedFile("comprobante.pdf", b"%PDF-1.4 prueba", content_type="application/pdf"),
        }
        datos.update(cambios)
        return self.client.post(reverse("comprobante_enviar", args=(self.casa.pk,)), datos)

    def test_periodo_actual_de_honduras_por_defecto_sin_campo_fecha(self):
        # En UTC ya es enero; en Honduras todavía es diciembre.
        with timezone.override("America/Tegucigalpa"), patch(
            "django.utils.timezone.now", return_value=datetime(2027, 1, 1, 3, tzinfo=datetime_timezone.utc),
        ):
            self.client.force_login(self.usuario)
            response = self.client.get(reverse("comprobante_enviar", args=(self.casa.pk,)))
        form = response.context["form"]
        self.assertEqual(form["anio"].value(), 2026)
        self.assertEqual(form["mes"].value(), 12)
        self.assertNotContains(response, 'name="fecha_pago"')
        self.assertNotContains(response, 'name="cuota_id"')
        self.assertNotContains(response, "Fecha de registro")
        self.assertNotContains(response, 'name="referencia"')
        self.assertEqual(form["metodo_pago"].value(), "TRANSFERENCIA")

    def test_sin_cuotas_permite_intentar_envio_y_muestra_error_visible(self):
        self.cuota.delete()
        self.client.force_login(self.usuario)
        response = self.client.get(reverse("comprobante_enviar", args=(self.casa.pk,)))
        self.assertNotContains(response, "disabled")
        self.assertNotContains(response, "No tienes cuotas pendientes")
        response = self.enviar()
        self.assertContains(response, 'data-form-errors')
        self.assertContains(response, "aún no tiene una cuota de vigilancia configurada")
        self.assertFalse(ComprobantePago.objects.exists())

    def test_fallo_guardando_archivo_muestra_error_y_permite_reintentar(self):
        with patch("django.core.files.storage.FileSystemStorage._save", side_effect=OSError("disco no disponible")):
            response = self.enviar()
        self.assertContains(response, "No pudimos guardar tu comprobante")
        self.assertContains(response, 'data-form-errors')
        self.assertFalse(ComprobantePago.objects.exists())
        self.assertEqual(self.enviar().status_code, 302)

    def test_envio_sin_referencia_aparece_en_historial_del_cliente(self):
        response = self.enviar(referencia="", comentario="Comprobante de prueba")
        self.assertEqual(response.status_code, 302)
        comprobante = ComprobantePago.objects.get()
        self.assertEqual(comprobante.referencia, "")
        response = self.client.get(response.url)
        self.assertContains(response, "Comprobante de Octubre 2026 enviado para revisión.")
        self.assertContains(response, "Pendiente de revisión")

    def test_fecha_automatica_y_periodo_seleccionado_se_guardan_separados(self):
        with patch("django.utils.timezone.localdate", return_value=date(2026, 11, 11)):
            response = self.enviar(fecha_pago="2000-01-01", cuota_id="999999")
        self.assertEqual(response.status_code, 302)
        comprobante = ComprobantePago.objects.get()
        self.assertEqual(comprobante.fecha_pago, date(2026, 11, 11))
        self.assertEqual(list(comprobante.cuotas.all()), [self.cuota])
        self.assertEqual(comprobante.cuotas.get().mes, 10)
        self.assertEqual(comprobante.estado, ComprobantePago.Estado.PENDIENTE)
        self.assertIsNone(comprobante.pago_id)

    def test_periodo_es_obligatorio_y_conserva_la_seleccion_si_hay_error(self):
        response = self.enviar(anio="")
        self.assertEqual(response.status_code, 200)
        self.assertIn("anio", response.context["form"].errors)
        self.assertEqual(response.context["form"]["mes"].value(), "10")
        self.assertFalse(ComprobantePago.objects.exists())

    def test_no_acepta_periodo_sin_cuota_pendiente(self):
        response = self.enviar(mes=9)
        self.assertEqual(response.status_code, 200)
        self.assertIn("mes", response.context["form"].errors)
        self.assertFalse(ComprobantePago.objects.exists())

    def test_no_acepta_mes_invalido(self):
        response = self.enviar(mes=13)
        self.assertIn("mes", response.context["form"].errors)
        self.assertFalse(ComprobantePago.objects.exists())

    def test_no_acepta_cuota_pagada_o_anulada(self):
        for estado in (CuotaMensual.Estado.PAGADA, CuotaMensual.Estado.ANULADA):
            self.cuota.estado = estado
            self.cuota.saldo = 0 if estado == CuotaMensual.Estado.PAGADA else 500
            self.cuota.save()
            response = self.enviar()
            self.assertIn("mes", response.context["form"].errors)
            self.assertFalse(ComprobantePago.objects.exists())

    def test_periodo_de_otra_persona_no_se_puede_seleccionar(self):
        otro = Responsable.objects.create(nombre_completo="Otra persona", identidad="9999999999999")
        otra_casa = Casa.objects.create(colonia=self.colonia, codigo="P2", responsable_actual=otro)
        cuota_ajena = CuotaMensual.objects.create(
            casa=otra_casa, responsable=otro, colonia=self.colonia, anio=2026, mes=9,
            monto_original=500, saldo=500,
        )
        response = self.enviar(mes=9, cuota_id=str(cuota_ajena.pk))
        self.assertIn("mes", response.context["form"].errors)
        self.assertFalse(ComprobantePago.objects.exists())

    def test_no_acepta_monto_mayor_al_saldo_del_periodo(self):
        response = self.enviar(monto="500.01")
        self.assertIn("monto", response.context["form"].errors)
        self.assertFalse(ComprobantePago.objects.exists())

    def test_permite_abono_al_periodo(self):
        response = self.enviar(monto="100.00")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(ComprobantePago.objects.get().monto, Decimal("100"))
        self.cuota.refresh_from_db()
        self.assertEqual(self.cuota.saldo, Decimal("500"))

    def test_archivo_se_guarda_por_anio_mes_y_se_puede_leer(self):
        response = self.enviar()
        self.assertEqual(response.status_code, 302)
        comprobante = ComprobantePago.objects.get()
        self.assertRegex(comprobante.archivo.name, r"^comprobantes/\d{4}/\d{2}/comprobante.*\.pdf$")
        self.assertTrue(comprobante.archivo.url.startswith("/media/comprobantes/"))
        with comprobante.archivo.open("rb") as archivo:
            self.assertEqual(archivo.read(), b"%PDF-1.4 prueba")

    def test_rechaza_extension_no_permitida(self):
        response = self.enviar(archivo=SimpleUploadedFile("prueba.exe", b"no permitido"))
        self.assertIn("archivo", response.context["form"].errors)
        self.assertFalse(ComprobantePago.objects.exists())

    def test_rechaza_archivo_mayor_a_ocho_mb(self):
        response = self.enviar(archivo=SimpleUploadedFile("prueba.pdf", b"x" * (8 * 1024 * 1024 + 1)))
        self.assertIn("archivo", response.context["form"].errors)
        self.assertFalse(ComprobantePago.objects.exists())

