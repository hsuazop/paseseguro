from unittest.mock import patch
from datetime import date
from io import BytesIO
from tempfile import TemporaryDirectory

from django.contrib.auth import authenticate
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image

from accesos.models import Vehiculo
from accounts.models import User, UsuarioColonia
from colonias.models import Casa, Colonia
from facturacion.models import ComprobantePago, Pago, TarifaColonia
from .models import ComprobanteInscripcion, RegistroPublico, Responsable
from .registro_publico import VILLA_OLIMPICA, activar_inscripcion


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", DEFAULT_FROM_EMAIL="avisos@example.com")
class RegistroPublicoTests(TestCase):
    def setUp(self):
        self.villa = Colonia.objects.create(nombre=VILLA_OLIMPICA)
        self.otra = Colonia.objects.create(nombre="Otra residencial")
        self.url = reverse("registro_villa_olimpica")
        self.datos = {"nombre_completo": "Ana López", "codigo_casa": "Bloque A, casa 8"}

    def test_publico_correo_acceso_y_alta_inmediata(self):
        self.assertContains(self.client.get(self.url), self.villa.nombre)
        datos = dict(self.datos, correo="Ana@Example.com", colonia=self.otra.pk, rol="ADMINISTRADOR",
                     agregar_vehiculo="1", **{"vehiculo-placa": "abc 123", "vehiculo-tipo": "AUTOMOVIL"})
        respuesta = self.client.post(self.url, datos, follow=True)
        self.assertContains(respuesta, "Te has registrado exitosamente")
        item = RegistroPublico.objects.get()
        self.assertEqual(item.responsable.etapa_sector, 1)
        self.assertEqual(item.colonia, self.villa)
        self.assertTrue(item.confirmado)
        casa = Casa.objects.get(colonia=self.villa, responsable_actual=item.responsable)
        self.assertEqual(Vehiculo.objects.get(casa=casa).placa, "ABC123")
        self.assertEqual(len(mail.outbox), 1)
        mensaje = mail.outbox[0]
        self.assertEqual(mensaje.to, ["ana@example.com"])
        clave = mensaje.body.split("Contraseña temporal: ")[1].splitlines()[0]
        usuario = authenticate(username="ana@example.com", password=clave)
        self.assertEqual(usuario.rol, User.Rol.RESIDENTE)
        self.assertTrue(usuario.debe_cambiar_password)
        self.assertNotContains(respuesta, clave)
        self.client.post(self.url, datos)
        self.assertEqual(RegistroPublico.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(casa.responsable_actual.usuario, usuario)
        duplicado = self.client.post(self.url, dict(self.datos, correo="otra@example.com", codigo_casa=casa.codigo.lower()))
        self.assertIn("codigo_casa", duplicado.context["form"].errors)
        self.assertFalse(User.objects.filter(email="otra@example.com").exists())

    def test_sin_correo_muestra_credenciales_una_vez(self):
        respuesta = self.client.post(self.url, self.datos, follow=True)
        resultado = respuesta.context["resultado"]
        self.assertIsNotNone(authenticate(username=resultado["usuario"], password=resultado["clave"]))
        self.assertNotContains(self.client.get(self.url), resultado["clave"])
        self.assertEqual(len(mail.outbox), 0)

    def test_primer_ingreso_directo_al_portal_completo(self):
        self.client.post(self.url, dict(self.datos, correo="ana@example.com"))
        registro = RegistroPublico.objects.get()
        usuario = registro.responsable.usuario
        temporal = mail.outbox[0].body.split("Contraseña temporal: ")[1].splitlines()[0]
        self.client.post(reverse("login"), {"username": usuario.username, "password": temporal})
        nueva = "PruebaDeIngreso824!"
        inicio = self.client.post(reverse("cambiar_password_obligatorio"), {
            "old_password": temporal, "new_password1": nueva, "new_password2": nueva,
        }, follow=True)
        casa = Casa.objects.get(responsable_actual=registro.responsable)
        self.assertEqual(inicio.request["PATH_INFO"], reverse("portal_residente", args=[casa.pk]))
        for ruta in ("comprobante_enviar", "configurar_perfil", "mi_cuenta_casa", "visita_crear"):
            self.assertContains(inicio, f'href="{reverse(ruta, args=[casa.pk])}"')
        self.assertNotContains(inicio, "confirmando tu casa")
        perfil = self.client.post(reverse("configurar_perfil", args=[casa.pk]), {
            "nombre": "Ana", "apellido": "López", "correo": "ana@example.com", "telefono": "99887766",
        }, follow=True)
        self.assertContains(perfil, "Tu información fue actualizada")
        otro = Casa.objects.create(colonia=self.villa, codigo="Otra casa")
        self.assertEqual(self.client.get(reverse("portal_residente", args=[otro.pk])).status_code, 404)

    def test_activar_registro_anterior_una_vez_con_su_comprobante(self):
        usuario = User.objects.create_user("residente-anterior")
        vecino = Responsable.objects.create(nombre_completo="Vecino anterior", usuario=usuario)
        registro = RegistroPublico.objects.create(colonia=self.villa, responsable=vecino, descripcion_casa="B-12")
        adjunto = ComprobanteInscripcion.objects.create(registro=registro, archivo="comprobantes/anterior.png",
                                                       anio=2026, mes=11, monto=350, metodo_pago="TRANSFERENCIA")
        activar_inscripcion(registro.pk)
        activar_inscripcion(registro.pk)
        casa = Casa.objects.get(responsable_actual=vecino)
        self.assertEqual(casa.historial_responsables.count(), 1)
        comprobante = ComprobantePago.objects.get()
        self.assertEqual((comprobante.casa, comprobante.archivo.name), (casa, adjunto.archivo.name))
        self.assertEqual(comprobante.estado, ComprobantePago.Estado.PENDIENTE)

    def test_etapa_sector_opcional_y_limitada_a_cinco_opciones(self):
        pagina = self.client.get(self.url)
        self.assertContains(pagina, '<option value="1" selected>Etapa o sector 1</option>', html=True)
        for valor in ("0", "6", "texto"):
            respuesta = self.client.post(self.url, dict(self.datos, etapa_sector=valor))
            self.assertIn("etapa_sector", respuesta.context["form"].errors)
        self.assertFalse(RegistroPublico.objects.exists())
        self.client.post(self.url, dict(self.datos, etapa_sector=""))
        self.assertEqual(RegistroPublico.objects.get().responsable.etapa_sector, 1)

    def test_alta_con_comprobante_y_revision_del_mes(self):
        url = reverse("registro_villa_con_comprobante")
        self.assertContains(self.client.get(url), 'enctype="multipart/form-data"')
        self.assertNotContains(self.client.get(self.url), 'name="pago-archivo"')
        pagina = self.client.get(url)
        self.assertContains(pagina, 'name="banco"', count=1)
        self.assertContains(pagina, 'name="numero_cuenta"', count=1)
        datos = {**self.datos, "etapa_sector": "5", "banco": "BAC", "numero_cuenta": "001234567",
                 "pago-anio": 2027, "pago-mes": 4, "pago-monto": "350.00",
                 "pago-metodo_pago": "TRANSFERENCIA"}
        for archivo in (None, SimpleUploadedFile("foto.png", b"invalido")):
            respuesta = self.client.post(url, {**datos, **({"pago-archivo": archivo} if archivo else {})})
            self.assertIn("archivo", respuesta.context["comprobante"].errors)
            self.assertFalse(User.objects.exists())
        imagen = BytesIO()
        Image.new("RGB", (10, 10)).save(imagen, format="PNG")
        with TemporaryDirectory() as carpeta, self.settings(MEDIA_ROOT=carpeta):
            datos["pago-archivo"] = SimpleUploadedFile("copia.png", imagen.getvalue(), "image/png")
            respuesta = self.client.post(url, datos, follow=True)
            self.assertContains(respuesta, "Recibimos tu comprobante")
            registro = RegistroPublico.objects.get()
            self.assertEqual(registro.responsable.etapa_sector, 5)
            self.assertEqual((registro.responsable.banco, registro.responsable.numero_cuenta), ("BAC", "001234567"))
            registro.responsable.banco = "FICOHSA"
            registro.responsable.numero_cuenta = "000111"
            registro.responsable.save()
            self.assertEqual(registro.adjunto.archivo.read(), imagen.getvalue())
            registro.adjunto.archivo.close()
            self.assertTrue(registro.confirmado)
            tesorero = User.objects.create_user("tesorero", rol=User.Rol.TESORERO)
            UsuarioColonia.objects.create(usuario=tesorero, colonia=self.villa)
            self.client.force_login(tesorero)
            item = ComprobantePago.objects.get()
            self.assertEqual((item.banco, item.numero_cuenta), ("BAC", "001234567"))
            self.assertEqual(item.estado, ComprobantePago.Estado.PENDIENTE)
            self.assertEqual(item.enviado_por, registro.responsable.usuario)
            self.assertEqual(item.archivo.name, registro.adjunto.archivo.name)
            self.assertEqual(item.periodos_solicitados, [{"anio": 2027, "mes": 4}])
            self.assertFalse(Pago.objects.exists())
            TarifaColonia.objects.create(colonia=self.villa, monto=350, fecha_inicio=date(2027, 1, 1))
            self.client.post(reverse("comprobante_revisar", args=[item.pk]), {"estado": "APROBADO"})
            item.refresh_from_db()
            self.assertIsNotNone(item.pago_id)
            self.assertEqual((item.cuotas.get().anio, item.cuotas.get().mes), (2027, 4))

    def test_pagina_publica_con_y_sin_sesion(self):
        tesorero = User.objects.create_user("tesorero", rol=User.Rol.TESORERO)
        for usuario in (None, tesorero):
            with self.subTest(usuario=usuario):
                if usuario:
                    self.client.force_login(usuario)
                pagina = self.client.get(self.url)
                self.assertContains(pagina, "Residencial Segura")
                self.assertContains(pagina, 'src="/static/core/brand/icon.svg"')
                self.assertNotContains(pagina, 'id="sidebar"')
                self.assertNotContains(pagina, 'aria-label="Accesos rápidos"')
                self.assertContains(pagina, "Llena tus datos y describe tu casa")
                self.assertContains(pagina, "Es importante que escribas un correo que revises")

    @patch("residentes.services.send_mail", side_effect=OSError)
    def test_error_smtp_preserva_registro(self, enviar):
        respuesta = self.client.post(self.url, dict(self.datos, correo="ana@example.com"), follow=True)
        self.assertContains(respuesta, "el envío del correo falló")
        self.assertTrue(RegistroPublico.objects.exists())
