from datetime import date
from decimal import Decimal
from io import StringIO
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import User, UsuarioColonia
from colonias.models import Casa, Colonia
from residentes.models import Responsable
from facturacion.models import ComprobantePago, CuotaMensual, TarifaColonia
from facturacion.services.cuotas import asegurar_cuota, definir_tarifa


class CuotasAutomaticasTests(TestCase):
    def setUp(self):
        self.fecha = patch('django.utils.timezone.localdate', return_value=date(2026, 11, 14))
        self.fecha.start()
        self.addCleanup(self.fecha.stop)
        self.media = TemporaryDirectory()
        self.addCleanup(self.media.cleanup)
        setting = override_settings(MEDIA_ROOT=self.media.name)
        setting.enable()
        self.addCleanup(setting.disable)
        self.colonia = Colonia.objects.create(nombre='Cuotas automáticas')
        self.admin = User.objects.create_user('admin-auto', rol='ADMINISTRADOR')
        UsuarioColonia.objects.create(usuario=self.admin, colonia=self.colonia)
        self.user = User.objects.create_user('cliente-auto', rol='RESIDENTE')
        self.persona = Responsable.objects.create(nombre_completo='Cliente', identidad='0801999999999', usuario=self.user)
        self.casa = Casa.objects.create(colonia=self.colonia, codigo='001', responsable_actual=self.persona)
        self.tarifa = TarifaColonia.objects.create(colonia=self.colonia, monto=500, fecha_inicio=date(2026, 1, 1))

    def enviar(self, **extra):
        self.client.force_login(self.user)
        data = {'anio': 2026, 'mes': 11, 'monto': '200', 'metodo_pago': 'TRANSFERENCIA',
                'archivo': SimpleUploadedFile('comprobante.pdf', b'%PDF-prueba')}
        data.update(extra)
        return self.client.post(reverse('comprobante_enviar', args=[self.casa.pk]), data)

    def test_noviembre_sin_generacion_manual_acepta_abono_y_aprobacion(self):
        self.assertFalse(CuotaMensual.objects.exists())
        response = self.enviar()
        self.assertEqual(response.status_code, 302)
        comprobante = ComprobantePago.objects.get()
        cuota = comprobante.cuotas.get()
        self.assertEqual(cuota.saldo, Decimal('500'))
        self.client.force_login(self.admin)
        response = self.client.post(reverse('comprobante_revisar', args=[comprobante.pk]), {'estado': 'APROBADO'})
        self.assertEqual(response.status_code, 302)
        cuota.refresh_from_db()
        self.assertEqual(cuota.monto_pagado, Decimal('200'))
        self.assertEqual(cuota.saldo, Decimal('300'))
        self.assertEqual(cuota.estado, 'PARCIAL')

    def test_tarea_diaria_idempotente_y_cambio_de_anio(self):
        call_command('sincronizar_cuotas', stdout=StringIO())
        call_command('sincronizar_cuotas', stdout=StringIO())
        self.assertEqual(CuotaMensual.objects.count(), 1)
        with patch('django.utils.timezone.localdate', return_value=date(2027, 1, 1)):
            call_command('sincronizar_cuotas', stdout=StringIO())
        self.assertTrue(CuotaMensual.objects.filter(anio=2027, mes=1, monto_original=500).exists())

    def test_pago_anticipado_sin_limite_de_anios_precreados(self):
        response = self.enviar(anio=2032, mes=5)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(ComprobantePago.objects.get().cuotas.get().anio, 2032)

    def test_archivo_invalido_no_crea_cuota_anticipada(self):
        response = self.enviar(anio=2032, mes=5, archivo=SimpleUploadedFile('archivo.exe', b'no permitido'))
        self.assertIn('archivo', response.context['form'].errors)
        self.assertFalse(CuotaMensual.objects.filter(anio=2032, mes=5).exists())

    def test_sin_tarifa_no_afecta_otra_residencial(self):
        otra = Colonia.objects.create(nombre='Sin tarifa')
        persona = Responsable.objects.create(nombre_completo='Otra persona', identidad='0801888888888')
        Casa.objects.create(colonia=otra, codigo='001', responsable_actual=persona)
        call_command('sincronizar_cuotas', stdout=StringIO(), stderr=StringIO())
        self.assertTrue(CuotaMensual.objects.filter(colonia=self.colonia, mes=11).exists())
        self.assertFalse(CuotaMensual.objects.filter(colonia=otra).exists())

    def test_cambiar_tarifa_conserva_historial_y_aplica_a_nuevos_meses(self):
        anterior = asegurar_cuota(casa=self.casa, anio=2026, mes=10)
        definir_tarifa(colonia=self.colonia, monto=Decimal('600'), anio=2026, mes=12, usuario=self.admin)
        anterior.refresh_from_db()
        self.assertEqual(anterior.monto_original, Decimal('500'))
        nueva = asegurar_cuota(casa=self.casa, anio=2026, mes=12)
        self.assertEqual(nueva.monto_original, Decimal('600'))
        self.tarifa.refresh_from_db()
        self.assertEqual(self.tarifa.fecha_fin, date(2026, 11, 30))

    def test_mes_pagado_o_anulado_no_se_recrea(self):
        cuota = asegurar_cuota(casa=self.casa, anio=2026, mes=11)
        for estado in ('PAGADA', 'ANULADA'):
            cuota.estado = estado
            cuota.saldo = 0
            cuota.save()
            response = self.enviar()
            self.assertIn('mes', response.context['form'].errors)
        self.assertEqual(CuotaMensual.objects.count(), 1)
        self.assertFalse(ComprobantePago.objects.exists())

    def test_sin_tarifa_muestra_causa_y_no_crea_comprobante(self):
        self.tarifa.delete()
        response = self.enviar()
        self.assertContains(response, 'aún no tiene una cuota de vigilancia configurada')
        self.assertFalse(CuotaMensual.objects.exists())
        self.assertFalse(ComprobantePago.objects.exists())

    def test_unica_cuota_por_persona_incluso_con_dos_casas(self):
        otra = Casa.objects.create(colonia=self.colonia, codigo='002', responsable_actual=self.persona)
        a = asegurar_cuota(casa=self.casa, anio=2026, mes=11)
        b = asegurar_cuota(casa=otra, anio=2026, mes=11)
        self.assertEqual(a.pk, b.pk)

    def test_otros_residentes_no_pueden_cambiar_tarifa(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.post(reverse('tarifa_crear'), {}).status_code, 403)

    def test_cambio_por_formulario_no_requiere_cerrar_tarifa_anterior(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse('tarifa_crear'), {
            'colonia': self.colonia.pk, 'monto': '650', 'anio': 2026, 'mes': 12,
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(asegurar_cuota(casa=self.casa, anio=2026, mes=12).monto_original, Decimal('650'))
