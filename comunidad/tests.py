from django.test import TestCase
from django.urls import reverse

from accounts.models import User, UsuarioColonia
from colonias.models import Casa, Colonia
from comunidad.models import SolicitudMensaje
from residentes.models import Responsable


class ComunidadPermisosTests(TestCase):
    def setUp(self):
        self.colonia = Colonia.objects.create(nombre="Colonia Comunidad")
        self.residente = User.objects.create_user(username="comunidad", password="Clave2026!", rol=User.Rol.RESIDENTE)
        responsable = Responsable.objects.create(nombre_completo="Comunidad Demo", identidad="0202000000001", usuario=self.residente)
        self.casa = Casa.objects.create(colonia=self.colonia, codigo="C1", numero="1", responsable_actual=responsable)

    def test_residente_crea_solicitud_en_su_colonia(self):
        self.client.force_login(self.residente)
        response = self.client.post(
            reverse("solicitud_crear", kwargs={"casa_id": self.casa.pk}),
            {
                "tipo": SolicitudMensaje.Tipo.SOLICITUD,
                "visibilidad": SolicitudMensaje.Visibilidad.PRIVADA,
                "asunto": "Luminaria dañada",
                "mensaje": "La lámpara frente a mi casa no funciona.",
            },
        )
        self.assertEqual(response.status_code, 302)
        solicitud = SolicitudMensaje.objects.get()
        self.assertEqual(solicitud.colonia, self.colonia)
        self.assertEqual(solicitud.casa, self.casa)

    def test_tesorero_sin_colonia_no_ve_bandeja_de_otra_colonia(self):
        SolicitudMensaje.objects.create(
            colonia=self.colonia,
            casa=self.casa,
            usuario=self.residente,
            asunto="Privado",
            mensaje="Contenido",
        )
        tesorero = User.objects.create_user(username="administrador2", password="Clave2026!", rol=User.Rol.ADMINISTRADOR)
        otra = Colonia.objects.create(nombre="Otra Colonia")
        UsuarioColonia.objects.create(usuario=tesorero, colonia=otra)
        self.client.force_login(tesorero)
        response = self.client.get(reverse("bandeja_comunidad"))
        self.assertNotContains(response, "Privado")

