from django.test import Client, TestCase
from django.urls import reverse

from accounts.models import User, UsuarioColonia
from colonias.models import Casa, Colonia
from residentes.models import Responsable
from .models import Vehiculo, VehiculoColonia


class VehiculosGestionTests(TestCase):
    def setUp(self):
        self.colonia = Colonia.objects.create(nombre="Las Palmas")
        self.otra = Colonia.objects.create(nombre="Otra residencial")
        self.tesorero = User.objects.create_user("tesorero", rol="TESORERO")
        UsuarioColonia.objects.create(usuario=self.tesorero, colonia=self.colonia)
        self.residente = User.objects.create_user("residente", rol="RESIDENTE")
        self.persona = Responsable.objects.create(nombre_completo="Ana", identidad="123", usuario=self.residente)
        self.casa = Casa.objects.create(colonia=self.colonia, codigo="001", responsable_actual=self.persona)
        self.ajeno = Responsable.objects.create(nombre_completo="Vecino ajeno", identidad="456")
        self.casa_ajena = Casa.objects.create(colonia=self.otra, codigo="999", responsable_actual=self.ajeno)
        self.url = reverse("vehiculo_registrar_gestion")
        self.lista = reverse("vehiculos_residentes_gestion")
        self.datos = {"tipo_registro": "residente", "casa": self.casa.pk, "placa": "haa 1234", "tipo": "AUTOMOVIL"}
        self.client.force_login(self.tesorero)

    def test_menu_y_selector_muestran_ambos_tipos(self):
        response = self.client.get(self.url, {"tipo": "residente"})
        self.assertContains(response, reverse("padron_vehicular"))
        self.assertContains(response, self.lista)
        self.assertContains(response, "Padrón de la residencial")
        self.assertContains(response, "Vehículo de residente")
        casas = list(response.context["form"].fields["casa"].queryset)
        self.assertEqual(casas, [self.casa])

    def test_alta_residente_asigna_relaciones_y_aparece_en_portal(self):
        response = self.client.post(self.url, {**self.datos, "colonia": self.otra.pk, "responsable": self.ajeno.pk})
        self.assertRedirects(response, self.lista)
        vehiculo = Vehiculo.objects.get()
        self.assertEqual(vehiculo.placa, "HAA1234")
        self.assertEqual(vehiculo.colonia, self.colonia)
        self.assertEqual(vehiculo.responsable, self.persona)
        self.assertEqual(vehiculo.casa, self.casa)
        self.assertFalse(VehiculoColonia.objects.exists())
        self.assertContains(self.client.get(self.lista, {"q": "ana"}), "HAA1234")
        self.client.force_login(self.residente)
        self.assertContains(self.client.get(reverse("mis_vehiculos", args=[self.casa.pk])), "HAA1234")

    def test_alta_padron_no_crea_vehiculo_residente(self):
        response = self.client.post(self.url, {"tipo_registro": "padron", "colonia": self.otra.pk,
            "placa": "hbb 1234", "propietario": "Propietario", "activo": "on"})
        self.assertRedirects(response, reverse("padron_vehicular"))
        registro = VehiculoColonia.objects.get()
        self.assertEqual(registro.colonia, self.colonia)
        self.assertEqual(registro.placa, "HBB1234")
        self.assertFalse(Vehiculo.objects.exists())

    def test_rechaza_casa_ajena_inactiva_o_sin_responsable(self):
        inactiva = Casa.objects.create(colonia=self.colonia, codigo="002", activa=False, responsable_actual=self.persona)
        sin_persona = Casa.objects.create(colonia=self.colonia, codigo="003")
        for casa in (self.casa_ajena, inactiva, sin_persona):
            with self.subTest(casa=casa.pk):
                response = self.client.post(self.url, {**self.datos, "casa": casa.pk})
                self.assertEqual(response.status_code, 200)
                self.assertIn("casa", response.context["form"].errors)
        self.assertFalse(Vehiculo.objects.exists())

    def test_placa_duplicada_se_muestra_como_error(self):
        self.client.post(self.url, self.datos)
        response = self.client.post(self.url, {**self.datos, "placa": "HAA1234"})
        self.assertContains(response, "Esta placa ya está registrada")
        self.assertEqual(Vehiculo.objects.count(), 1)

    def test_listado_no_expone_otra_colonia(self):
        Vehiculo.objects.create(colonia=self.otra, casa=self.casa_ajena, responsable=self.ajeno, placa="HZZ9999")
        response = self.client.get(self.lista, {"colonia": self.otra.pk})
        self.assertNotContains(response, "HZZ9999")
        self.assertEqual(response.context["page_obj"].paginator.count, 0)

    def test_roles_sin_asignacion_csrf_y_tipo_invalido(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.tesorero)
        self.assertEqual(client.post(self.url, self.datos).status_code, 403)
        self.assertEqual(self.client.post(self.url, {**self.datos, "tipo_registro": "otro"}).status_code, 403)
        for rol in ("RESIDENTE", "GUARDIA"):
            user = User.objects.create_user(rol, rol=rol)
            self.client.force_login(user)
            self.assertEqual(self.client.get(self.lista).status_code, 403)
            self.assertEqual(self.client.post(self.url, self.datos).status_code, 403)
        self.client.force_login(self.tesorero)
        UsuarioColonia.objects.filter(usuario=self.tesorero).delete()
        self.assertEqual(self.client.post(self.url, self.datos).status_code, 403)
        self.assertFalse(Vehiculo.objects.exists())
