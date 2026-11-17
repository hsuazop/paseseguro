import base64
from unittest.mock import patch
from django.test import TestCase, Client, override_settings
from django.utils import timezone
from datetime import timedelta
from accounts.models import User, UsuarioColonia
from colonias.models import Colonia, Casa
from residentes.models import Responsable
from .models import AlertaSOS, SuscripcionPush, EntregaSOS
from .push import encolar, procesar_lote


class SOSPushTests(TestCase):
    def setUp(self):
        self.colonia=Colonia.objects.create(nombre='A')
        self.otra=Colonia.objects.create(nombre='B')
        self.residente=User.objects.create_user('residente',rol='RESIDENTE')
        responsable=Responsable.objects.create(nombre_completo='Residente',identidad='123',usuario=self.residente)
        self.casa=Casa.objects.create(colonia=self.colonia,codigo='A1',numero='1',responsable_actual=responsable)
        self.guardia=User.objects.create_user('guardia',rol='GUARDIA')
        self.asignacion=UsuarioColonia.objects.create(usuario=self.guardia,colonia=self.colonia)
        self.guard=Client();self.guard.force_login(self.guardia)
        self.payload={'endpoint':'https://fcm.googleapis.com/fcm/send/test','keys':{'p256dh':base64.urlsafe_b64encode(b'\x04'+b'x'*64).decode(),'auth':base64.urlsafe_b64encode(b'a'*16).decode()}}
        self.assertEqual(self.guard.post('/push/suscribir/',self.payload,content_type='application/json').status_code,200)
        self.alerta=AlertaSOS.objects.create(colonia=self.colonia,casa=self.casa,usuario=self.residente,mensaje='Ayuda')

    def test_encola_una_sola_entrega_y_solo_en_colonia(self):
        encolar(self.alerta);encolar(self.alerta)
        self.assertEqual(EntregaSOS.objects.count(),1)
        EntregaSOS.objects.all().delete()
        self.asignacion.colonia=self.otra;self.asignacion.save()
        encolar(self.alerta)
        self.assertFalse(EntregaSOS.objects.exists())

    def test_residente_no_puede_suscribirse_ni_leer_alertas(self):
        self.client.force_login(self.residente)
        self.assertEqual(self.client.post('/push/suscribir/',self.payload,content_type='application/json').status_code,403)
        self.assertEqual(self.client.get(f'/guardia/sos/{self.alerta.pk}/datos/').status_code,403)

    def test_endpoint_arbitrario_es_rechazado(self):
        for url in ['http://127.0.0.1/','https://attacker.test/','https://fcm.googleapis.com.attacker.test/','https://fcm.googleapis.com:123/']:
            self.payload['endpoint']=url
            self.assertEqual(self.guard.post('/push/suscribir/',self.payload,content_type='application/json').status_code,400)

    def test_otra_colonia_no_lee_ni_atiende(self):
        self.asignacion.colonia=self.otra;self.asignacion.save()
        self.assertEqual(self.guard.get(f'/guardia/sos/{self.alerta.pk}/datos/').status_code,404)
        self.assertEqual(self.guard.post(f'/guardia/sos/{self.alerta.pk}/',{'accion':'atender'}).status_code,404)

    def test_cerrar_sesion_desactiva(self):
        self.guard.post('/logout/')
        self.assertFalse(SuscripcionPush.objects.get().activa)
        encolar(self.alerta);self.assertFalse(EntregaSOS.objects.exists())

    def test_atender_registra_guardia_y_no_se_sobrescribe(self):
        url=f'/guardia/sos/{self.alerta.pk}/'
        self.guard.post(url,{'accion':'atender'})
        self.alerta.refresh_from_db()
        self.assertEqual(self.alerta.estado,'ATENDIENDO')
        self.assertEqual(self.alerta.atendido_por,self.guardia)
        self.assertIsNotNone(self.alerta.atendido_en)
        self.assertFalse(self.guard.get(url+'datos/').json()['active'])
        self.guard.post(url,{'accion':'cerrar'});self.alerta.refresh_from_db()
        self.assertEqual(self.alerta.estado,'CERRADA')

    def test_crear_sos_encola_y_muestra_datos(self):
        self.client.force_login(self.residente)
        r=self.client.post(f'/mi-cuenta/{self.casa.pk}/sos/',{'mensaje':'Necesito ayuda'})
        self.assertEqual(r.status_code,302)
        self.assertEqual(EntregaSOS.objects.count(),1)
        self.assertContains(self.guard.get(f'/guardia/sos/{self.alerta.pk}/'),'A1')

    def test_suscripcion_requiere_csrf(self):
        c=Client(enforce_csrf_checks=True);c.force_login(self.guardia)
        self.assertEqual(c.post('/push/suscribir/',self.payload,content_type='application/json').status_code,403)

    @override_settings(WEBPUSH_PRIVATE_KEY='test', WEBPUSH_PUBLIC_KEY='test', WEBPUSH_SUBJECT='mailto:test@example.com')
    @patch('pywebpush.webpush')
    def test_prueba_solo_dispositivo_propio_sin_crear_sos(self, send):
        data = {'endpoint': self.payload['endpoint']}
        before = AlertaSOS.objects.count()
        self.assertEqual(self.guard.post('/push/probar/', data, content_type='application/json').status_code, 200)
        self.assertEqual(send.call_args.kwargs['data'], '{"tipo": "prueba"}')
        self.assertEqual(AlertaSOS.objects.count(), before)
        self.assertEqual(self.guard.post('/push/probar/', data, content_type='application/json').status_code, 429)
        send.assert_called_once()

    @override_settings(WEBPUSH_PRIVATE_KEY='test', WEBPUSH_PUBLIC_KEY='test', WEBPUSH_SUBJECT='mailto:test@example.com')
    @patch('pywebpush.webpush')
    def test_prueba_no_envia_a_otro_dispositivo_o_sesion(self, send):
        data = {'endpoint': self.payload['endpoint']}
        other = Client(); other.force_login(self.guardia)
        self.assertEqual(other.post('/push/probar/', data, content_type='application/json').status_code, 403)
        self.assertEqual(self.guard.post('/push/probar/', {'endpoint': 'https://example.com/'}, content_type='application/json').status_code, 403)
        self.client.force_login(self.residente)
        self.assertEqual(self.client.post('/push/probar/', data, content_type='application/json').status_code, 403)
        send.assert_not_called()

    @override_settings(WEBPUSH_PRIVATE_KEY='test', WEBPUSH_PUBLIC_KEY='test', WEBPUSH_SUBJECT='mailto:test@example.com')
    @patch('pywebpush.webpush', side_effect=TimeoutError)
    def test_prueba_informa_fallo_del_proveedor(self, send):
        response = self.guard.post('/push/probar/', {'endpoint': self.payload['endpoint']}, content_type='application/json')
        self.assertEqual(response.status_code, 502)
        self.assertIn('error', response.json())

    @override_settings(WEBPUSH_PRIVATE_KEY='test',WEBPUSH_PUBLIC_KEY='test',WEBPUSH_SUBJECT='mailto:test@example.com')
    @patch('pywebpush.webpush')
    def test_proveedor_acepta_no_equivale_a_atendida(self,send):
        encolar(self.alerta);procesar_lote()
        send.assert_called_once()
        self.assertEqual(EntregaSOS.objects.get().estado,'ACEPTADA')
        self.alerta.refresh_from_db();self.assertEqual(self.alerta.estado,'NUEVA')

    @override_settings(WEBPUSH_PRIVATE_KEY='test',WEBPUSH_PUBLIC_KEY='test',WEBPUSH_SUBJECT='mailto:test@example.com')
    @patch('pywebpush.webpush',side_effect=TimeoutError)
    def test_reintentos_persistentes(self,send):
        encolar(self.alerta);procesar_lote()
        item=EntregaSOS.objects.get()
        self.assertEqual(item.estado,'PENDIENTE');self.assertEqual(item.intentos,1)
        self.assertGreater(item.siguiente,timezone.now())

    @override_settings(WEBPUSH_PRIVATE_KEY='test',WEBPUSH_PUBLIC_KEY='test',WEBPUSH_SUBJECT='mailto:test@example.com')
    @patch('pywebpush.webpush')
    def test_no_envia_tras_logout_o_cambio_password(self,send):
        encolar(self.alerta);self.guardia.set_password('Nueva-clave');self.guardia.save()
        procesar_lote();send.assert_not_called()
        self.assertEqual(EntregaSOS.objects.get().estado,'CANCELADA')
