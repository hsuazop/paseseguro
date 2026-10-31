from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from colonias.models import Casa, Colonia
from residentes.models import Responsable
from visitas.models import Visita
from visitas.tokens import crear_token_residente, leer_token_residente


class VisitasSeguridadTests(TestCase):
    def setUp(self):
        self.colonia = Colonia.objects.create(nombre="Colonia Prueba")
        self.usuario = User.objects.create_user(
            username="0801000000001",
            identidad="0801000000001",
            password="ClaveSegura2026!",
            rol=User.Rol.RESIDENTE,
        )
        self.responsable = Responsable.objects.create(
            nombre_completo="Residente Uno",
            identidad="0801000000001",
            usuario=self.usuario,
        )
        self.casa = Casa.objects.create(
            colonia=self.colonia,
            codigo="001",
            numero="1",
            responsable_actual=self.responsable,
        )
        otro_usuario = User.objects.create_user(
            username="0801000000002",
            identidad="0801000000002",
            password="ClaveSegura2026!",
            rol=User.Rol.RESIDENTE,
        )
        otro = Responsable.objects.create(
            nombre_completo="Residente Dos",
            identidad="0801000000002",
            usuario=otro_usuario,
        )
        self.otra_casa = Casa.objects.create(colonia=self.colonia, codigo="002", numero="2", responsable_actual=otro)

    def test_residente_no_puede_listar_visitas_de_otra_casa(self):
        self.client.force_login(self.usuario)
        response = self.client.get(reverse("visitas_lista", kwargs={"casa_id": self.otra_casa.pk}))
        self.assertEqual(response.status_code, 404)

    def test_crear_visita_la_asocia_a_casa_y_usuario(self):
        self.client.force_login(self.usuario)
        inicio = timezone.localtime() + timedelta(hours=1)
        response = self.client.post(
            reverse("visita_crear", kwargs={"casa_id": self.casa.pk}),
            {
                "tipo": Visita.Tipo.VISITA,
                "temporalidad": Visita.Temporalidad.UNICA,
                "nombre_visitante": "Carlos Visitante",
                "fecha_inicio": inicio.strftime("%Y-%m-%dT%H:%M"),
                "max_usos": 1,
                "max_personas": 2,
            },
        )
        self.assertEqual(response.status_code, 302)
        visita = Visita.objects.get()
        self.assertEqual(visita.casa, self.casa)
        self.assertEqual(visita.creado_por, self.usuario)

    def test_token_residente_contiene_solo_ids_verificables(self):
        token = crear_token_residente(usuario_id=self.usuario.pk, casa_id=self.casa.pk, instante=30)
        payload = leer_token_residente(token)
        self.assertEqual(payload["u"], self.usuario.pk)
        self.assertEqual(payload["c"], self.casa.pk)

