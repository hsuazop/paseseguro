"""Complete user journeys against an isolated Django test database."""
from datetime import timedelta
from tempfile import TemporaryDirectory
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, TransactionTestCase, Client, override_settings, skipUnlessDBFeature
from django.urls import reverse
from django.utils import timezone
from accounts.models import User, UsuarioColonia
from facturacion import test_revision_comprobantes as fixtures
from facturacion.models import ComprobantePago, Pago, CuotaMensual
from facturacion.services import anular_pago
from reservas.models import AreaComun, Reserva
from visitas.models import Visita, RegistroAcceso
from comunidad.models import SolicitudMensaje


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend', DEFAULT_FROM_EMAIL='prueba@example.com')
class SimulacionSistemaTests(TestCase):
    def setUp(self):
        fixtures.RevisionComprobanteTests.setUp(self)
        self.item.delete()
        self.media=TemporaryDirectory();self.addCleanup(self.media.cleanup)
        settings=override_settings(MEDIA_ROOT=self.media.name);settings.enable();self.addCleanup(settings.disable)
        self.residente=Client();self.residente.force_login(self.user)
        self.guardia=User.objects.create_user('guardia_sim',rol='GUARDIA')
        UsuarioColonia.objects.create(usuario=self.guardia,colonia=self.colonia)
        self.guard=Client();self.guard.force_login(self.guardia)

    def enviar(self,monto=500,mes=10):
        response=self.residente.post(reverse('comprobante_enviar',args=[self.casa.pk]),{
            'anio':2026,'mes':mes,'monto':monto,'metodo_pago':'TRANSFERENCIA',
            'archivo':SimpleUploadedFile('prueba.pdf',b'%PDF-1.4 simulacion',content_type='application/pdf')})
        self.assertEqual(response.status_code,302)
        return ComprobantePago.objects.latest('pk')

    def revisar(self,item,estado='APROBADO',mes=10):
        return self.client.post(reverse('comprobante_revisar',args=[item.pk]),{'estado':estado,'anio':2026,'mes':mes,'comentario_revision':'Verificado en simulación'})

    def estado_tesoreria(self):
        response=self.client.get(reverse('tesoreria'),{'anio':2026,'mes':10})
        self.assertEqual(response.status_code,200)
        return next(row['estado'] for row in response.context['filas'] if row['casa'].pk==self.casa.pk)

    def test_ciclo_completo_residente_tesorero_saldo_recibo_y_correo(self):
        self.assertEqual(self.estado_tesoreria(),'PENDIENTE')
        item=self.enviar();self.cuota.refresh_from_db()
        self.assertEqual(self.cuota.saldo,500);self.assertFalse(Pago.objects.exists())
        self.assertEqual(self.estado_tesoreria(),'POR_VALIDAR')
        self.assertEqual(self.revisar(item).status_code,302)
        item.refresh_from_db();self.cuota.refresh_from_db()
        self.assertEqual(self.cuota.saldo,0);self.assertEqual(self.cuota.estado,'PAGADA')
        self.assertEqual(self.estado_tesoreria(),'PAGADA')
        response=self.residente.get(reverse('mi_cuenta_casa',args=[self.casa.pk]),{'anio':2026})
        self.assertEqual(response.context['pagado_anio'],500)
        pdf=self.residente.get(reverse('recibo_pdf',args=[item.pago_id]))
        self.assertEqual(pdf.status_code,200);self.assertTrue(pdf.content.startswith(b'%PDF'))
        self.assertEqual(len(mail.outbox),1)
        self.revisar(item);self.assertEqual(Pago.objects.count(),1)

    def test_abonos_hasta_completar_sin_marcar_pagado_antes(self):
        self.revisar(self.enviar(200));self.cuota.refresh_from_db()
        self.assertEqual(self.cuota.saldo,300);self.assertEqual(self.cuota.estado,'PARCIAL')
        self.assertNotEqual(self.estado_tesoreria(),'PAGADA')
        self.revisar(self.enviar(300));self.cuota.refresh_from_db()
        self.assertEqual(self.cuota.saldo,0);self.assertEqual(self.estado_tesoreria(),'PAGADA')
        self.assertEqual(Pago.objects.count(),2)

    def test_rechazo_no_cobra_y_nuevo_envio_si_se_puede_aprobar(self):
        self.revisar(self.enviar(),estado='RECHAZADO');self.cuota.refresh_from_db()
        self.assertEqual(self.cuota.saldo,500);self.assertFalse(Pago.objects.exists())
        self.revisar(self.enviar());self.assertEqual(self.estado_tesoreria(),'PAGADA')

    def test_dos_comprobantes_mismo_saldo_no_generan_sobrepago(self):
        primero=self.enviar();segundo=self.enviar()
        self.revisar(primero);self.revisar(segundo)
        self.assertEqual(Pago.objects.count(),1);self.cuota.refresh_from_db();self.assertEqual(self.cuota.saldo,0)

    def test_rechazado_reciente_no_oculta_otro_comprobante_pendiente(self):
        self.enviar();self.revisar(self.enviar(),estado='RECHAZADO')
        self.assertEqual(self.estado_tesoreria(),'POR_VALIDAR')

    def test_anulacion_restaura_deuda_y_correo_no_dice_aprobado(self):
        item=self.enviar();self.revisar(item);item.refresh_from_db()
        anular_pago(pago=item.pago,motivo='Corrección de registro',usuario=self.tesorero)
        self.cuota.refresh_from_db();self.assertEqual(self.cuota.saldo,500)
        self.assertEqual(self.estado_tesoreria(),'PENDIENTE')
        self.client.post(reverse('comprobante_enviar_correo',args=[item.pk]))
        self.assertIn('anulado',mail.outbox[-1].body.lower())
        self.assertContains(self.residente.get(reverse('comprobantes_residente',args=[self.casa.pk])),'Pago anulado')

    def test_estado_de_cuenta_con_anio_invalido_no_falla(self):
        self.assertEqual(self.residente.get(reverse('mi_cuenta_casa',args=[self.casa.pk]),{'anio':'incorrecto'}).status_code,200)

    def test_reserva_aprobar_cancelar_y_no_resucitar(self):
        area=AreaComun.objects.create(colonia=self.colonia,nombre='Salón',capacidad=10)
        data={'area':area.pk,'fecha':(timezone.localdate()+timedelta(days=2)).isoformat(),'hora_inicio':'10:00','hora_fin':'12:00','personas':3}
        self.assertEqual(self.residente.post(reverse('reserva_crear',args=[self.casa.pk]),data).status_code,302)
        reserva=Reserva.objects.get()
        self.client.post(reverse('reserva_revisar',args=[reserva.pk]),{'estado':'APROBADA'})
        reserva.refresh_from_db();self.assertEqual(reserva.estado,'APROBADA')
        self.residente.post(reverse('reserva_cancelar',args=[self.casa.pk,reserva.pk]))
        self.client.post(reverse('reserva_revisar',args=[reserva.pk]),{'estado':'APROBADA'})
        reserva.refresh_from_db();self.assertEqual(reserva.estado,'CANCELADA')

    def test_reserva_horas_faltantes_muestra_error_sin_500(self):
        area=AreaComun.objects.create(colonia=self.colonia,nombre='Salón',capacidad=10)
        self.assertEqual(self.residente.post(reverse('reserva_crear',args=[self.casa.pk]),{'area':area.pk,'fecha':'2027-01-02','personas':2}).status_code,200)
        self.assertFalse(Reserva.objects.exists())

    def test_visita_guardia_agota_uso_y_cancelada_no_entra(self):
        visita=Visita.objects.create(casa=self.casa,creado_por=self.user,nombre_visitante='Invitado',fecha_inicio=timezone.now()-timedelta(minutes=5))
        url=reverse('visita_registrar_acceso',args=[visita.pk])
        self.guard.post(url);self.guard.post(url)
        visita.refresh_from_db();self.assertEqual(visita.usos_actuales,1);self.assertEqual(RegistroAcceso.objects.count(),1)
        self.residente.post(reverse('visita_cancelar',args=[self.casa.pk,visita.pk]));self.guard.post(url)
        self.assertEqual(RegistroAcceso.objects.count(),1)

    def test_solicitud_residente_respuesta_tesoreria(self):
        self.residente.post(reverse('solicitud_crear',args=[self.casa.pk]),{'tipo':'SOLICITUD','visibilidad':'PRIVADA','asunto':'Luminaria','mensaje':'Reparar lámpara'})
        item=SolicitudMensaje.objects.get()
        self.client.post(reverse('solicitud_responder',args=[item.pk]),{'estado':'RESUELTO','respuesta':'Reparada'})
        item.refresh_from_db();self.assertEqual(item.estado,'RESUELTO');self.assertEqual(item.respondido_por,self.tesorero)


class AprobacionConcurrenteTests(TransactionTestCase):
    def setUp(self):
        fixtures.RevisionComprobanteTests.setUp(self)

    @skipUnlessDBFeature('has_select_for_update')
    def test_dos_tesoreros_simultaneos_solo_registran_un_pago(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from django.db import connections, close_old_connections
        from django.core.exceptions import ValidationError
        from facturacion.services.comprobantes import revisar_comprobante
        barrier=Barrier(2)
        def aprobar():
            close_old_connections()
            try:
                usuario=User.objects.get(pk=self.tesorero.pk)
                barrier.wait(timeout=10)
                revisar_comprobante(self.item.pk,{'estado':'APROBADO','anio':2026,'mes':10,'comentario_revision':'Prueba concurrente'},usuario)
                return 'registrado'
            except ValidationError:
                return 'bloqueado'
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            resultados=list(pool.map(lambda _:aprobar(),range(2)))
        self.assertCountEqual(resultados,['registrado','bloqueado'])
        self.assertEqual(Pago.objects.count(),1)
        self.cuota.refresh_from_db();self.assertEqual(self.cuota.saldo,0)
