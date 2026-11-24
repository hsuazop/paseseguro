from datetime import date
from datetime import timedelta
from unittest.mock import patch
from django.core import mail
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.utils import timezone
from accounts.models import User, UsuarioColonia
from colonias.models import Casa, Colonia
from residentes.models import Responsable
from .models import ComprobantePago, ComprobanteCuota, CuotaMensual, Pago, TarifaColonia


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', DEFAULT_FROM_EMAIL='avisos@example.com')
class RevisionComprobanteTests(TestCase):
    def setUp(self):
        self.colonia=Colonia.objects.create(nombre='Residencial de prueba')
        self.user=User.objects.create_user('residente',rol='RESIDENTE',email='residente@example.com')
        self.responsable=Responsable.objects.create(nombre_completo='Residente',identidad='123',usuario=self.user)
        self.casa=Casa.objects.create(colonia=self.colonia,codigo='A1',responsable_actual=self.responsable)
        self.tesorero=User.objects.create_user('tesorero',rol='TESORERO')
        UsuarioColonia.objects.create(usuario=self.tesorero,colonia=self.colonia)
        TarifaColonia.objects.create(colonia=self.colonia,monto=500,fecha_inicio=date(2026,1,1))
        self.cuota=CuotaMensual.objects.create(casa=self.casa,colonia=self.colonia,responsable=self.responsable,anio=2026,mes=10,monto_original=500,saldo=500)
        self.item=ComprobantePago.objects.create(casa=self.casa,colonia=self.colonia,responsable=self.responsable,enviado_por=self.user,monto=500,metodo_pago='TRANSFERENCIA',archivo='comprobantes/prueba.png')
        ComprobanteCuota.objects.create(comprobante=self.item,cuota=self.cuota)
        self.url=f'/comprobantes/{self.item.pk}/revisar/'
        self.correo=f'/comprobantes/{self.item.pk}/correo/'
        self.client.force_login(self.tesorero)

    def aceptar(self, **datos):
        return self.client.post(self.url, {'estado':'APROBADO','anio':2026,'mes':11,**datos})

    def test_corrige_periodo_registra_y_notifica(self):
        self.assertContains(self.client.get(reverse('comprobantes_gestion')), 'name="referencia"')
        self.assertEqual(self.aceptar(referencia="001-BAC").status_code,302)
        self.item.refresh_from_db();self.cuota.refresh_from_db()
        self.assertEqual(self.item.estado,'APROBADO');self.assertIsNotNone(self.item.pago_id)
        self.assertEqual(self.item.referencia, "001-BAC")
        self.assertEqual(self.item.pago.referencia, "001-BAC")
        self.assertContains(self.client.get(self.url), "001-BAC")
        self.assertEqual(self.cuota.saldo,500)
        self.assertEqual(self.item.cuotas.get().mes,11)
        self.assertEqual(self.item.cuotas.get().saldo,0)
        self.assertEqual(self.item.periodos_solicitados,[{'anio':2026,'mes':10}])
        self.assertEqual(len(mail.outbox),1);self.assertEqual(mail.outbox[0].to,['residente@example.com'])
        self.assertIn('Pagado',mail.outbox[0].body)

    def test_referencia_duplicada_no_aplica_otro_mes(self):
        self.aceptar(referencia="001 BC")
        segundo = ComprobantePago.objects.create(
            casa=self.casa, colonia=self.colonia, responsable=self.responsable, enviado_por=self.user,
            monto=500, metodo_pago='TRANSFERENCIA', archivo='comprobantes/segundo.png',
        )
        url = reverse('comprobante_revisar', args=[segundo.pk])
        datos = {'anio': 2026, 'mes': 12, 'estado': 'APROBADO', 'referencia': '001bc'}
        self.assertContains(self.client.post(url, datos), "referencia bancaria ya se usó")
        segundo.refresh_from_db()
        self.assertEqual(segundo.estado, 'PENDIENTE')
        self.assertFalse(segundo.cuotas.exists())
        self.assertEqual(Pago.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(self.client.post(url, {**datos, 'referencia': ''}).status_code, 302)

    def test_doble_aceptacion_no_duplica_pago_ni_correo(self):
        self.aceptar();response=self.aceptar(mes=12)
        self.assertContains(response,'ya está registrado')
        self.assertEqual(Pago.objects.count(),1);self.assertEqual(len(mail.outbox),1)
        self.item.refresh_from_db();self.assertEqual(self.item.cuotas.get().mes,11)
        self.client.post(self.url,{'estado':'RECHAZADO'})
        self.item.refresh_from_db();self.assertEqual(self.item.estado,'APROBADO')

    def test_sin_correo_registra_sin_enviar(self):
        self.user.email='';self.user.save()
        self.assertEqual(self.aceptar().status_code,302)
        self.assertEqual(len(mail.outbox),0);self.assertEqual(Pago.objects.count(),1)

    def test_correo_manual_no_aprueba_ni_cambia_periodo(self):
        response=self.client.post(self.correo,{'estado':'APROBADO','anio':2027,'mes':1})
        self.assertEqual(response.status_code,302)
        self.item.refresh_from_db();self.assertEqual(self.item.estado,'PENDIENTE')
        self.assertIsNone(self.item.pago_id);self.assertEqual(self.item.cuotas.get(),self.cuota)
        self.assertEqual(len(mail.outbox),1);self.assertIn('Pendiente',mail.outbox[0].body)
        self.client.post(self.correo);self.assertEqual(len(mail.outbox),1)

    def test_fallback_correo_responsable(self):
        self.user.email='';self.user.save()
        self.responsable.correo='contacto@example.com';self.responsable.save()
        self.client.post(self.correo)
        self.assertEqual(mail.outbox[0].to,['contacto@example.com'])

    @patch('facturacion.services.comprobantes.send_mail',side_effect=OSError)
    def test_fallo_smtp_no_revierte_pago(self, send):
        self.assertEqual(self.aceptar().status_code,302)
        self.item.refresh_from_db();self.assertIsNotNone(self.item.pago_id)
        self.assertTrue(self.item.correo_error);self.assertIsNone(self.item.correo_enviado_en)

    def test_saldo_insuficiente_revierte_cambio_periodo(self):
        self.item.monto=600;self.item.save()
        self.assertContains(self.aceptar(),'supera el saldo')
        self.assertFalse(Pago.objects.exists());self.assertEqual(self.item.cuotas.get(),self.cuota)
        self.assertFalse(CuotaMensual.objects.filter(mes=11).exists())
        self.assertEqual(len(mail.outbox),0)

    def test_aislamiento_roles_csrf_y_metodo(self):
        self.assertEqual(self.client.get(self.correo).status_code,405)
        c=Client(enforce_csrf_checks=True);c.force_login(self.tesorero)
        self.assertEqual(c.post(self.correo).status_code,403)
        self.client.force_login(self.user);self.assertEqual(self.client.post(self.correo).status_code,403)
        self.client.force_login(self.tesorero)
        UsuarioColonia.objects.filter(usuario=self.tesorero).delete()
        self.assertEqual(self.client.post(self.correo).status_code,404)
        self.assertEqual(self.aceptar().status_code,404)

    def test_tabla_miniatura_periodos_y_botones(self):
        response=self.client.get('/comprobantes/')
        for fragment in ['data-preview-type="image"','Confirmar pago y generar recibo','Enviar correo',f'form="revision-{self.item.pk}"','name="anio"','name="mes"']:
            self.assertContains(response,fragment)
        self.assertEqual(self.client.get(self.url).status_code,200)

    def test_periodo_parcial_rechazado(self):
        response=self.client.post(self.url,{'estado':'APROBADO','anio':2026})
        self.assertContains(response,'Indica tanto')
        self.assertFalse(Pago.objects.exists())

    def test_inicio_tesorero_solicitudes_y_orden_por_antiguedad_o_residente(self):
        self.assertRedirects(self.client.get(reverse('dashboard')), reverse('comprobantes_gestion'))
        persona = Responsable.objects.create(nombre_completo='Ana', identidad='456')
        casa = Casa.objects.create(colonia=self.colonia, codigo='A2', responsable_actual=persona)
        nuevo = ComprobantePago.objects.create(casa=casa, colonia=self.colonia,
            responsable=persona, enviado_por=self.user, monto=500,
            metodo_pago='TRANSFERENCIA', archivo='comprobantes/ana.png')
        ComprobantePago.objects.filter(pk=self.item.pk).update(created_at=timezone.now()-timedelta(days=2))
        response = self.client.get(reverse('comprobantes_gestion'))
        self.assertEqual([c.pk for c in response.context['comprobantes']], [self.item.pk, nuevo.pk])
        response = self.client.get(reverse('comprobantes_gestion'), {'orden': 'residente'})
        self.assertEqual([c.pk for c in response.context['comprobantes']], [nuevo.pk, self.item.pk])
        response = self.client.get(reverse('comprobantes_gestion'), {'residente': persona.pk})
        self.assertEqual([c.pk for c in response.context['comprobantes']], [nuevo.pk])
        otra = Colonia.objects.create(nombre='Otra colonia')
        Casa.objects.filter(pk=casa.pk).update(colonia=otra)
        ComprobantePago.objects.filter(pk=nuevo.pk).update(colonia=otra)
        response = self.client.get(reverse('comprobantes_gestion'), {'colonia': otra.pk})
        self.assertEqual([c.pk for c in response.context['comprobantes']], [self.item.pk])
        self.assertNotContains(response, 'Ana')
        self.assertEqual(self.client.post(reverse('comprobante_revisar', args=[nuevo.pk]), {'estado':'APROBADO'}).status_code, 404)

    def test_confirmacion_muestra_recibo_y_periodo_pagado_al_residente(self):
        response = self.client.get(reverse('comprobantes_gestion'))
        self.assertNotContains(response, 'Ver recibo')
        self.assertEqual(self.aceptar(mes=10).status_code, 302)
        self.item.refresh_from_db()
        self.cuota.refresh_from_db()
        self.assertEqual(self.cuota.estado, 'PAGADA')
        self.assertEqual(self.cuota.saldo, 0)
        self.assertEqual(self.item.estado_visible, 'Pagado')
        recibo = reverse('recibo_detalle', args=[self.item.pago_id])
        response = self.client.get(reverse('comprobantes_gestion'))
        self.assertNotContains(response, recibo)
        self.assertEqual(response.context['page_obj'].paginator.count, 0)
        response = self.client.get(reverse('comprobantes_gestion'), {'estado': 'APROBADO'})
        self.assertEqual(response.context['page_obj'].paginator.count, 0)
        response = self.client.get(reverse('tesoreria'), {'anio': 2026, 'mes': 10})
        self.assertContains(response, recibo)
        self.assertContains(response, 'Ver comprobante / correo')
        self.assertEqual(response.context['recaudado'], 500)
        self.assertNotContains(response, 'Confirmar pago y generar recibo')
        self.assertEqual(self.client.get(recibo).status_code, 200)
        self.client.force_login(self.user)
        response = self.client.get(reverse('comprobantes_residente', args=[self.casa.pk]))
        self.assertContains(response, 'Pagado')
        self.assertContains(response, recibo)
        self.assertEqual(self.client.get(recibo).status_code, 200)
        response = self.client.get(reverse('mi_cuenta_casa', args=[self.casa.pk]), {'anio': 2026})
        octubre = next(c for c in response.context['cuotas'] if c['numero'] == 10)
        self.assertEqual(octubre['cuota'].estado, 'PAGADA')

    def test_correo_siempre_disponible_sin_destinatario_y_sin_pago(self):
        self.user.email = ''
        self.user.save()
        response = self.client.get(reverse('comprobantes_gestion'))
        self.assertContains(response, '<button class="btn btn-outline-primary mt-2">Enviar correo</button>', html=True)
        self.client.post(self.correo)
        self.item.refresh_from_db()
        self.assertEqual(self.item.estado, 'PENDIENTE')
        self.assertIsNone(self.item.pago_id)
        self.assertEqual(len(mail.outbox), 0)

    def test_abono_no_marca_mes_completo_y_anulacion_restaura_estado(self):
        from .services import anular_pago
        self.item.monto = 200
        self.item.save()
        self.aceptar(mes=10)
        self.cuota.refresh_from_db()
        self.item.refresh_from_db()
        self.assertEqual(self.cuota.estado, 'PARCIAL')
        self.assertEqual(self.cuota.saldo, 300)
        anular_pago(pago=self.item.pago, motivo='Prueba de anulación', usuario=self.tesorero)
        self.item.refresh_from_db()
        self.cuota.refresh_from_db()
        self.assertEqual(self.item.estado_visible, 'Pago anulado')
        self.assertEqual(self.cuota.estado, 'PENDIENTE')
