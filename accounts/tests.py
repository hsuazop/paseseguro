from django.test import TestCase
from django.urls import reverse

from colonias.models import Colonia

from .models import User, UsuarioColonia


class GestionUsuariosTests(TestCase):
    def setUp(self):
        self.colonia = Colonia.objects.create(nombre="Residencial Prueba")
        self.admin = User.objects.create_user(
            "admin-prueba",
            password="ClaveSegura1!",
            rol=User.Rol.ADMINISTRADOR,
        )
        UsuarioColonia.objects.create(usuario=self.admin, colonia=self.colonia)
        self.client.force_login(self.admin)

    def test_pantalla_de_usuarios_muestra_los_tipos_de_alta(self):
        response = self.client.get(reverse("usuarios_lista"))
        self.assertContains(response, "Crear guardia")
        self.assertContains(response, "Crear tesorero")
        self.assertContains(response, "Registrar residente")

    def test_manifiesto_disponible_durante_cambio_de_password_obligatorio(self):
        self.admin.debe_cambiar_password = True
        self.admin.save(update_fields=("debe_cambiar_password",))
        response = self.client.get(reverse("app_manifest"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["name"], "Residencial Segura")
        self.assertEqual(self.client.get(reverse("android_assetlinks")).status_code, 200)
        self.assertRedirects(self.client.get(reverse("inicio")), reverse("cambiar_password_obligatorio"), fetch_redirect_response=False)

    def test_administrador_crea_tesorero_en_su_residencial(self):
        response = self.client.post(reverse("usuario_crear") + "?rol=TESORERO", {
            "username": "tesorero-prueba",
            "first_name": "Teresa",
            "last_name": "Rera",
            "identidad": "0801199012345",
            "rol": User.Rol.TESORERO,
            "colonia": self.colonia.pk,
            "password1": "ClaveSegura1!",
            "password2": "ClaveSegura1!",
            "is_active": "on",
        })
        self.assertRedirects(response, reverse("usuarios_lista"))
        tesorero = User.objects.get(username="tesorero-prueba")
        self.assertEqual(tesorero.rol, User.Rol.TESORERO)
        self.assertTrue(UsuarioColonia.objects.filter(usuario=tesorero, colonia=self.colonia, activa=True).exists())

    def test_usuario_operativo_requiere_residencial(self):
        response = self.client.post(reverse("usuario_crear"), {
            "username": "guardia-prueba",
            "first_name": "Gina",
            "last_name": "Guardia",
            "rol": User.Rol.GUARDIA,
            "password1": "ClaveSegura1!",
            "password2": "ClaveSegura1!",
            "is_active": "on",
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Residencial asignada")
        self.assertFalse(User.objects.filter(username="guardia-prueba").exists())
