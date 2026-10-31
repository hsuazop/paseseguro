from django.test import TestCase
from django.urls import reverse

from accounts.models import User, UsuarioColonia
from colonias.models import Casa, Colonia
from residentes.models import Responsable

from .models import RegistroVehicular, Vehiculo


class ControlVehicularTests(TestCase):
    def setUp(self):
        self.colonia = Colonia.objects.create(nombre="Residencial Accesos")
        self.otra_colonia = Colonia.objects.create(nombre="Residencial Ajena")
        self.guardia = User.objects.create_user("guardia-test", password="Clave2026!", rol=User.Rol.GUARDIA)
        UsuarioColonia.objects.create(usuario=self.guardia, colonia=self.colonia)
        self.residente = User.objects.create_user(
            "0505000000001",
            identidad="0505000000001",
            password="Clave2026!",
            rol=User.Rol.RESIDENTE,
        )
        self.responsable = Responsable.objects.create(
            nombre_completo="Persona Vehículo",
            identidad="0505000000001",
            usuario=self.residente,
        )
        self.casa = Casa.objects.create(
            colonia=self.colonia,
            codigo="V01",
            numero="1",
            responsable_actual=self.responsable,
        )
        self.vehiculo = Vehiculo.objects.create(
            responsable=self.responsable,
            colonia=self.colonia,
            casa=self.casa,
            placa="HAA1234",
            marca="Toyota",
            color="Blanco",
        )

    def test_guardia_es_redirigido_a_panel_operativo(self):
        self.client.force_login(self.guardia)
        response = self.client.get(reverse("dashboard"))
        self.assertRedirects(response, reverse("dashboard_guardia"))

    def test_guardia_no_puede_acceder_a_finanzas(self):
        self.client.force_login(self.guardia)
        self.assertEqual(self.client.get(reverse("pagos_lista")).status_code, 403)

    def test_entrada_reconoce_vehiculo_de_residente(self):
        self.client.force_login(self.guardia)
        response = self.client.post(
            reverse("registrar_entrada"),
            {
                "colonia": self.colonia.pk,
                "placa": "haa 1234",
                "tipo_acceso": RegistroVehicular.TipoAcceso.VISITANTE,
                "personas": 1,
            },
        )
        self.assertEqual(response.status_code, 302)
        registro = RegistroVehicular.objects.get()
        self.assertEqual(registro.vehiculo, self.vehiculo)
        self.assertEqual(registro.responsable_destino, self.responsable)
        self.assertEqual(registro.tipo_acceso, RegistroVehicular.TipoAcceso.RESIDENTE)

    def test_residente_solo_ve_sus_vehiculos(self):
        otro = Responsable.objects.create(nombre_completo="Otra Persona", identidad="0505000000002")
        otra_casa = Casa.objects.create(colonia=self.colonia, codigo="V02", numero="2", responsable_actual=otro)
        self.client.force_login(self.residente)
        response = self.client.get(reverse("mis_vehiculos", args=(otra_casa.pk,)))
        self.assertEqual(response.status_code, 404)

