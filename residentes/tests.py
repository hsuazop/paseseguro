from io import BytesIO

from django.test import TestCase
from django.urls import reverse
from openpyxl import Workbook

from accounts.models import User, UsuarioColonia
from colonias.models import Casa, Colonia
from facturacion.models import CuentaPagoColonia
from colonias.services import ENCABEZADOS, analizar_importacion, guardar_importacion
from .forms import ResponsableForm
from .models import Responsable
from .services import crear_usuario_residente


class CorreoVecinoTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user("admin", rol=User.Rol.ADMINISTRADOR)
        self.colonia = Colonia.objects.create(nombre="Las Palmas")
        UsuarioColonia.objects.create(usuario=self.admin, colonia=self.colonia)

    def test_alta_exige_correo_valido(self):
        for correo in ("", "sin-arroba"):
            form = ResponsableForm({"nombre_completo": "Ana Lopez", "identidad": "123", "correo": correo})
            self.assertFalse(form.is_valid())
            self.assertIn("correo", form.errors)

    def test_inicio_muestra_solo_cuentas_oficiales_y_prioriza_preferencia(self):
        villa = Colonia.objects.create(nombre="Residencial Villa Olímpica")
        vecino = Responsable.objects.create(nombre_completo="Ana", banco="FICOHSA", numero_cuenta="999")
        usuario, _ = crear_usuario_residente(vecino)
        usuario.debe_cambiar_password = False
        usuario.save()
        casa = Casa.objects.create(colonia=villa, codigo="A", numero="1", responsable_actual=vecino)
        for colonia, banco, numero in ((villa, "BAC", "0011"), (villa, "Ficohsa", "0022"), (self.colonia, "BAC", "0033")):
            CuentaPagoColonia.objects.create(colonia=colonia, banco=banco, numero_cuenta=numero, titular="Tesorería")
        self.client.force_login(usuario)
        response = self.client.get(reverse("portal_residente", args=[casa.pk]))
        self.assertEqual([c.numero_cuenta for c in response.context["cuentas_vigilancia"]], ["0022", "0011"])
        self.assertContains(response, 'data-copiar="0022"')
        self.assertNotContains(response, 'data-copiar="999"')

    def test_alta_guarda_correo_con_y_sin_usuario(self):
        self.client.force_login(self.admin)
        for crear_usuario in (False, True):
            datos = {"nombre_completo": "Ana Lopez", "identidad": f"123{crear_usuario}",
                     "correo": "ana@example.com", "activo": "on", "banco": "BAC", "numero_cuenta": "001234"}
            if crear_usuario:
                datos["crear_usuario"] = "on"
            response = self.client.post(reverse("responsable_crear"), datos)
            self.assertEqual(response.status_code, 200)
            vecino = Responsable.objects.get(identidad=datos["identidad"])
            self.assertEqual(vecino.correo, "ana@example.com")
            self.assertEqual((vecino.banco, vecino.numero_cuenta), ("BAC", "001234"))
            if crear_usuario:
                self.assertEqual(vecino.usuario.email, vecino.correo)
            else:
                self.assertIsNone(vecino.usuario_id)

    def test_perfil_actualiza_correo_en_cuenta_y_vecino_y_no_permite_borrarlo(self):
        vecino = Responsable.objects.create(nombre_completo="Ana Lopez", identidad="123", correo="ana@example.com")
        usuario, _ = crear_usuario_residente(vecino)
        usuario.debe_cambiar_password = False
        usuario.save()
        casa = Casa.objects.create(colonia=self.colonia, codigo="1", numero="1", responsable_actual=vecino)
        self.client.force_login(usuario)
        url = reverse("configurar_perfil", args=(casa.pk,))
        response = self.client.post(url, {"nombre": "Ana", "apellido": "Lopez", "correo": "nuevo@example.com",
                                          "banco": "FICOHSA", "numero_cuenta": "00001234"})
        self.assertEqual(response.status_code, 302)
        vecino.refresh_from_db()
        usuario.refresh_from_db()
        self.assertEqual(vecino.correo, "nuevo@example.com")
        self.assertEqual((vecino.banco, vecino.numero_cuenta), ("FICOHSA", "00001234"))
        self.assertEqual(usuario.email, vecino.correo)
        response = self.client.post(url, {"nombre": "Ana", "correo": ""})
        self.assertIn("correo", response.context["form"].errors)
        vecino.refresh_from_db()
        self.assertEqual(vecino.correo, "nuevo@example.com")

    def archivo_importacion(self, correo):
        libro = Workbook()
        libro.active.append(ENCABEZADOS)
        libro.active.append(["Las Palmas", "1", "1", "", "Ana Lopez", "123", "99999999", "", correo])
        archivo = BytesIO()
        libro.save(archivo)
        archivo.seek(0)
        return archivo

    def test_importacion_rechaza_correo_ausente_o_invalido(self):
        for correo in ("", "incorrecto"):
            _, errores = analizar_importacion(self.archivo_importacion(correo), [self.colonia])
            self.assertTrue(any("correo" in error for error in errores))

    def test_importacion_guarda_correo_en_vecino_y_usuario(self):
        datos, errores = analizar_importacion(self.archivo_importacion("ana@example.com"), [self.colonia])
        self.assertFalse(errores)
        guardar_importacion(datos, self.admin)
        vecino = Responsable.objects.get(identidad="123")
        self.assertEqual(vecino.correo, "ana@example.com")
        self.assertEqual(vecino.usuario.email, vecino.correo)
