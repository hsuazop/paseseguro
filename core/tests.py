from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase, override_settings
from django.contrib.staticfiles import finders
from django.urls import reverse
from django.template.loader import render_to_string


class ErrorPresentationTests(SimpleTestCase):
    @override_settings(DEBUG=False, ALLOWED_HOSTS=['testserver'])
    def test_pagina_no_encontrada_muestra_accion_para_volver(self):
        response = self.client.get('/pagina-inexistente-qa/')
        self.assertContains(response, 'No encontramos esta página', status_code=404)
        self.assertContains(response, 'Volver al inicio', status_code=404)

    def test_csrf_expirado_muestra_formulario_para_reintentar(self):
        from django.test import Client
        response = Client(enforce_csrf_checks=True).post(reverse('login'), {})
        self.assertContains(response, 'Abrir formulario nuevamente', status_code=403)
        self.assertNotContains(response, 'CSRF verification failed', status_code=403)

    def test_resumen_escapa_errores_y_enlaza_campos(self):
        from django import forms
        class Formulario(forms.Form):
            nombre = forms.CharField(label='Nombre')
        form = Formulario(data={})
        html = render_to_string('components/form_errors.html', {'form': form})
        self.assertIn('href="#id_nombre"', html)
        self.assertIn('role="alert"', html)


class IdentidadAppTests(SimpleTestCase):
    def test_vinculo_android_publico_contiene_paquete_y_certificado_validos(self):
        response = self.client.get(reverse("android_assetlinks"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/json")
        self.assertNotIn("Location", response)
        statement = response.json()[0]
        self.assertIn("delegate_permission/common.handle_all_urls", statement["relation"])
        self.assertEqual(statement["target"]["namespace"], "android_app")
        self.assertEqual(statement["target"]["package_name"], "com.paseseguro.app")
        for fingerprint in statement["target"]["sha256_cert_fingerprints"]:
            self.assertRegex(fingerprint, r"^(?:[0-9A-F]{2}:){31}[0-9A-F]{2}$")
        self.assertEqual(self.client.post(reverse("android_assetlinks")).status_code, 405)

    def test_manifiesto_publico_con_inicio_e_iconos_de_android(self):
        response = self.client.get(reverse("app_manifest"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/manifest+json")
        manifest = response.json()
        self.assertEqual(manifest["name"], "Residencial Segura")
        self.assertEqual(manifest["start_url"], reverse("inicio"))
        self.assertEqual(manifest["scope"], reverse("inicio"))
        self.assertEqual(manifest["display"], "standalone")
        self.assertTrue(any(icon["sizes"] == "192x192" for icon in manifest["icons"]))
        self.assertTrue(any(icon["sizes"] == "512x512" and icon["purpose"] == "maskable" for icon in manifest["icons"]))
        for icon in manifest["icons"]:
            self.assertTrue(finders.find("core/brand/" + icon["src"].rsplit("/", 1)[-1]))

    def test_login_incluye_identidad_y_manifiesto(self):
        response = self.client.get(reverse("login"))
        self.assertContains(response, 'rel="manifest"')
        self.assertContains(response, reverse("app_manifest"))
        self.assertContains(response, 'brand/icon-192.png')


class InicioAppTests(TestCase):
    def test_inicio_sin_sesion_pide_acceso(self):
        self.assertRedirects(self.client.get(reverse("inicio")), reverse("login") + "?next=/", fetch_redirect_response=False)

    def test_inicio_lleva_al_panel_del_rol(self):
        from accounts.models import User

        for rol, destino in ((User.Rol.RESIDENTE, "mi_cuenta"), (User.Rol.GUARDIA, "dashboard_guardia"), (User.Rol.TESORERO, "comprobantes_gestion")):
            with self.subTest(rol=rol):
                user = User.objects.create_user("inicio-" + rol, rol=rol)
                self.client.force_login(user)
                self.assertRedirects(self.client.get(reverse("inicio")), reverse(destino), fetch_redirect_response=False)


class VerificarMediaTests(SimpleTestCase):
    def test_verifica_carpeta_configurada_sin_dejar_archivos_de_prueba(self):
        with TemporaryDirectory() as folder:
            root = Path(folder) / "uploads"
            with override_settings(MEDIA_ROOT=root, MEDIA_URL="/media/"):
                output = StringIO()
                call_command("verificar_media", stdout=output)
            self.assertTrue(root.is_dir())
            self.assertEqual(list(root.iterdir()), [])
            self.assertIn("comprobantes/%Y/%m/", output.getvalue())

    def test_rechaza_media_en_carpeta_de_static(self):
        with TemporaryDirectory() as folder, override_settings(MEDIA_ROOT=folder, STATIC_ROOT=folder):
            with self.assertRaises(CommandError):
                call_command("verificar_media", stdout=StringIO())
