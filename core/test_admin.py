from datetime import date
from decimal import Decimal
from io import StringIO
from unittest.mock import patch

from django.apps import apps
from django.contrib import admin
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import RequestFactory, TestCase
from django.urls import reverse

from accounts.models import User
from colonias.models import Casa, Colonia
from residentes.models import Responsable
from facturacion.models import AplicacionPago, ComprobanteCuota, ComprobantePago, CuotaMensual, Pago


class DjangoAdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_superuser('admin-qa', password='PruebaAdmin!8742')
        cls.colonia = Colonia.objects.create(nombre='Residencial QA')
        cls.persona = Responsable.objects.create(nombre_completo='Residente QA', identidad='0801999999998')
        cls.casa = Casa.objects.create(colonia=cls.colonia, codigo='QA001', numero='1', responsable_actual=cls.persona)
        cls.cuota = CuotaMensual.objects.create(casa=cls.casa, colonia=cls.colonia, responsable=cls.persona,
                                               anio=2026, mes=10, monto_original=500, monto_pagado=200,
                                               saldo=300, estado='PARCIAL')
        cls.pago = Pago.objects.create(numero_recibo='QA-2026-1', casa=cls.casa, colonia=cls.colonia,
                                      responsable=cls.persona, fecha_pago=date(2026, 10, 1), monto_total=200,
                                      metodo_pago='EFECTIVO', usuario_que_registra=cls.user)
        AplicacionPago.objects.create(pago=cls.pago, cuota_mensual=cls.cuota, monto_aplicado=200)
        cls.comprobante = ComprobantePago.objects.create(casa=cls.casa, colonia=cls.colonia,
            responsable=cls.persona, enviado_por=cls.user, monto=100, metodo_pago='TRANSFERENCIA', archivo='qa.pdf')
        ComprobanteCuota.objects.create(comprobante=cls.comprobante, cuota=cls.cuota)

    def setUp(self):
        self.client.force_login(self.user)
        self.request = RequestFactory().get('/admin/')
        self.request.user = self.user

    def test_todos_los_modelos_estan_registrados_y_tienen_busqueda(self):
        for model in apps.get_models():
            with self.subTest(model=model._meta.label):
                self.assertIn(model, admin.site._registry)
                self.assertTrue(admin.site._registry[model].search_fields)

    def test_todos_los_listados_busquedas_formularios_y_detalles_abren(self):
        for model, model_admin in admin.site._registry.items():
            opts = model._meta
            prefix = f'admin:{opts.app_label}_{opts.model_name}'
            with self.subTest(model=opts.label):
                self.assertEqual(self.client.get(reverse(prefix + '_changelist')).status_code, 200)
                self.assertEqual(self.client.get(reverse(prefix + '_changelist'), {'q': 'QA'}).status_code, 200)
                if model_admin.has_add_permission(self.request):
                    self.assertEqual(self.client.get(reverse(prefix + '_add')).status_code, 200)
                obj = model.objects.first()
                if obj:
                    self.assertEqual(self.client.get(reverse(prefix + '_change', args=[obj.pk])).status_code, 200)

    def test_portada_tiene_marca_y_resumen(self):
        response = self.client.get(reverse('admin:index'))
        self.assertContains(response, 'Residencia Segura')
        self.assertContains(response, 'Residenciales y casas')
        self.assertContains(response, 'Todo tu sistema, en un solo lugar')
        self.assertContains(response, 'core/admin.css')

    def test_persona_sin_staff_no_ingresa_al_admin(self):
        user = User.objects.create_user('residente-qa', rol='RESIDENTE')
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse('admin:index')).status_code, 302)

    def test_cuota_nueva_calcula_saldo_sin_editar_importes_derivados(self):
        response = self.client.post(reverse('admin:facturacion_cuotamensual_add'), {
            'colonia': self.colonia.pk, 'casa': self.casa.pk, 'responsable': self.persona.pk,
            'anio': 2026, 'mes': 12, 'monto_original': '500.00', '_save': 'Guardar',
        })
        self.assertEqual(response.status_code, 302)
        cuota = CuotaMensual.objects.get(anio=2026, mes=12)
        self.assertEqual(cuota.saldo, Decimal('500'))
        self.assertEqual(cuota.monto_pagado, Decimal('0'))

    def test_estado_comprobante_no_se_puede_aprobar_sin_procesar_pago(self):
        response = self.client.post(reverse('admin:facturacion_comprobantepago_change', args=[self.comprobante.pk]), {'estado': 'APROBADO'})
        self.assertEqual(response.status_code, 403)
        self.comprobante.refresh_from_db()
        self.assertEqual(self.comprobante.estado, 'PENDIENTE')
        response = self.client.get(reverse('admin:facturacion_comprobantepago_change', args=[self.comprobante.pk]))
        self.assertContains(response, reverse('comprobante_revisar', args=[self.comprobante.pk]))

    def test_creacion_superusuario_es_idempotente_y_no_imprime_contrasena(self):
        password = 'TemporalSegura!8742-Zx'
        output = StringIO()
        with patch('sys.stdin', StringIO(password + '\n')):
            call_command('crear_superusuario_admin', username='superadmin-qa', stdout=output)
        user = User.objects.get(username='superadmin-qa')
        self.assertTrue(user.is_superuser and user.is_staff and user.is_active)
        self.assertTrue(user.check_password(password))
        self.assertNotIn(password, output.getvalue())
        with patch('sys.stdin', StringIO(password + '\n')):
            call_command('crear_superusuario_admin', username='superadmin-qa', stdout=output)
        with patch('sys.stdin', StringIO('Otra!8742-Zx\n')):
            with self.assertRaises(CommandError):
                call_command('crear_superusuario_admin', username='superadmin-qa', stdout=output)
