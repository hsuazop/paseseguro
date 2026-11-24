from unittest.mock import patch

from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import User, UsuarioColonia
from colonias.models import Casa, Colonia
from .models import RegistroPublico, Responsable


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class DirectorioTesoreriaTests(TestCase):
    def setUp(self):
        self.villa = Colonia.objects.create(nombre="Villa")
        self.otra = Colonia.objects.create(nombre="Otra")
        self.tesorero = User.objects.create_user("tesorero", rol=User.Rol.TESORERO)
        UsuarioColonia.objects.create(usuario=self.tesorero, colonia=self.villa)
        self.client.force_login(self.tesorero)
        self.usuario = User.objects.create_user("ana@example.com", email="ana@example.com")
        self.ana = Responsable.objects.create(nombre_completo="Ana Sol", correo=self.usuario.email, usuario=self.usuario)
        RegistroPublico.objects.create(responsable=self.ana, colonia=self.villa, descripcion_casa="Entrada norte")
        self.url = reverse("tesoreria_residente_acceso", args=[self.ana.pk])
        self.lista = reverse("tesoreria_residentes")

    def guardar(self, accion, **datos):
        version = self.client.get(self.url).context["version"]
        return self.client.post(self.url, {"accion": accion, "version": version, **datos}, follow=True)

    def test_directorio_aislado_incluye_inscripciones_y_varias_casas(self):
        otro = Responsable.objects.create(nombre_completo="Persona ajena")
        Casa.objects.create(colonia=self.otra, codigo="Privada", responsable_actual=otro)
        vecino = Responsable.objects.create(nombre_completo="Luis Paz")
        for codigo in ("A-1", "A-2"):
            Casa.objects.create(colonia=self.villa, codigo=codigo, responsable_actual=vecino)
        pagina = self.client.get(self.lista, {"colonia": self.otra.pk})
        self.assertEqual(pagina.context["page_obj"].paginator.count, 2)
        self.assertContains(pagina, "Pendiente de confirmar")
        self.assertContains(pagina, "A-2")
        self.assertNotContains(pagina, otro.nombre_completo)
        for texto in ("Entrada norte", "A-1"):
            self.assertEqual(self.client.get(self.lista, {"q": texto}).context["page_obj"].paginator.count, 1)
        url_ajena = reverse("tesoreria_residente_acceso", args=[otro.pk])
        self.assertEqual(self.client.post(url_ajena, {"accion": "clave"}).status_code, 404)
        self.client.force_login(self.usuario)
        self.assertEqual(self.client.get(self.lista).status_code, 403)

    def test_correo_y_reset_temporal_solo_una_vez(self):
        self.guardar("correo", correo="Nueva@Example.com")
        self.usuario.refresh_from_db()
        self.ana.refresh_from_db()
        self.assertEqual((self.usuario.username, self.usuario.email, self.ana.correo), ("nueva@example.com",) * 3)
        version = self.client.get(self.url).context["version"]
        datos = {"version": version, "accion": "clave"}
        vista = self.client.post(self.url, datos, follow=True)
        clave = vista.context["resultado"]["clave"]
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password(clave))
        self.assertTrue(self.usuario.debe_cambiar_password)
        self.assertEqual(mail.outbox[0].to, [self.ana.correo])
        self.assertIn(clave, mail.outbox[0].body)
        self.assertNotContains(self.client.get(self.url), clave)
        self.client.post(self.url, datos)
        self.assertEqual(len(mail.outbox), 1)

    def test_cuentas_compartidas_y_privilegiadas_solo_lectura(self):
        casa = Casa.objects.create(colonia=self.otra, codigo="privada", responsable_actual=self.ana)
        self.assertEqual(self.client.post(self.url, {"accion": "clave"}).status_code, 403)
        casa.delete()
        self.usuario.is_staff = True
        self.usuario.save()
        self.assertEqual(self.client.post(self.url, {"accion": "correo", "correo": "x@example.com"}).status_code, 403)

    def test_correo_duplicado_y_usuario_por_identidad(self):
        User.objects.create_user("otro", email="ocupado@example.com")
        self.assertContains(self.guardar("correo", correo="ocupado@example.com"), "ya está en uso")
        self.usuario.username = "08010001"
        self.usuario.save()
        self.guardar("correo", correo="")
        self.usuario.refresh_from_db()
        self.assertEqual((self.usuario.username, self.usuario.email), ("08010001", ""))
        self.assertTrue(self.guardar("clave").context["resultado"]["clave"])
        self.assertEqual(len(mail.outbox), 0)

    @patch("residentes.services.send_mail", side_effect=OSError)
    def test_fallo_de_correo_conserva_clave_para_entrega(self, enviar):
        vista = self.guardar("clave")
        self.assertContains(vista, "Falló el envío")
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password(vista.context["resultado"]["clave"]))
