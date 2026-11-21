from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from PIL import Image
from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse

from accounts.models import User, UsuarioColonia
from colonias.models import Colonia
from .models import FotoEntrada, RegistroVehicular


class FotosEntradaTests(TestCase):
    def setUp(self):
        self.folder = TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        field = FotoEntrada._meta.get_field("archivo")
        original = field.storage
        field.storage = FileSystemStorage(location=self.folder.name)
        self.addCleanup(setattr, field, "storage", original)
        self.colonia = Colonia.objects.create(nombre="Fotos")
        self.otra = Colonia.objects.create(nombre="Ajena")
        self.guardia = User.objects.create_user("guardia", rol="GUARDIA")
        UsuarioColonia.objects.create(usuario=self.guardia, colonia=self.colonia)
        self.client.force_login(self.guardia)
        self.url = reverse("registrar_entrada")
        self.datos = {"placa": "HAA1234", "tipo_acceso": "VISITANTE", "personas": 1}

    def foto(self, name="foto.jpg", formato="JPEG"):
        stream = BytesIO()
        Image.new("RGB", (20, 20), "blue").save(stream, format=formato)
        return SimpleUploadedFile(name, stream.getvalue(), content_type="image/jpeg" if formato == "JPEG" else "image/png")

    def test_entrada_guarda_varias_fotos_y_enlaces_en_historial(self):
        response = self.client.post(self.url, {**self.datos, "fotos": [self.foto(), self.foto("segunda.png", "PNG")]})
        self.assertRedirects(response, reverse("dashboard_guardia"))
        registro = RegistroVehicular.objects.get()
        self.assertEqual(registro.fotos.count(), 2)
        self.assertEqual(registro.guardia_entrada, self.guardia)
        self.assertEqual(registro.colonia, self.colonia)
        gallery = reverse("fotos_entrada", args=[registro.pk])
        self.assertContains(self.client.get(reverse("historial_accesos")), gallery)
        self.assertContains(self.client.get(reverse("dashboard_guardia")), "Ver fotos (2)")
        self.assertContains(self.client.get(gallery), "Ampliar foto 2")
        for foto in registro.fotos.all():
            self.assertTrue(Path(foto.archivo.path).is_file())
            response = self.client.get(reverse("foto_entrada_archivo", args=[foto.pk]))
            self.assertEqual(response.status_code, 200)
            self.assertIn(response["Content-Type"], ("image/jpeg", "image/png"))
            self.assertIn("no-store", response["Cache-Control"])
            self.assertEqual(response["X-Content-Type-Options"], "nosniff")
            self.assertTrue(b''.join(response.streaming_content))
            response.close()

    def test_fotos_opcionales(self):
        self.assertEqual(self.client.post(self.url, self.datos).status_code, 302)
        self.assertEqual(RegistroVehicular.objects.count(), 1)
        self.assertFalse(FotoEntrada.objects.exists())

    def test_valida_todas_las_fotos_no_solo_la_ultima(self):
        mala = SimpleUploadedFile("falsa.jpg", b"no es una imagen", content_type="image/jpeg")
        response = self.client.post(self.url, {**self.datos, "fotos": [mala, self.foto()]})
        self.assertIn("fotos", response.context["form"].errors)
        self.assertFalse(RegistroVehicular.objects.exists())
        self.assertFalse(FotoEntrada.objects.exists())

    def test_limite_cantidad_y_tamano(self):
        response = self.client.post(self.url, {**self.datos, "fotos": [self.foto() for _ in range(9)]})
        self.assertIn("fotos", response.context["form"].errors)
        grande = SimpleUploadedFile("grande.jpg", b"x" * (8 * 1024 * 1024 + 1), content_type="image/jpeg")
        response = self.client.post(self.url, {**self.datos, "fotos": [grande]})
        self.assertIn("fotos", response.context["form"].errors)
        self.assertFalse(RegistroVehicular.objects.exists())

    def test_error_de_otros_campos_no_guarda_archivos(self):
        response = self.client.post(self.url, {**self.datos, "personas": 0, "fotos": [self.foto()]})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(FotoEntrada.objects.exists())
        self.assertFalse(any(Path(self.folder.name).rglob('*')))

    def test_fallo_al_guardar_revierte_entrada_y_limpia_fotos(self):
        original = FotoEntrada.save
        llamadas = 0
        def guardar(instance, *args, **kwargs):
            nonlocal llamadas
            llamadas += 1
            if llamadas == 2:
                raise OSError("Error simulado")
            return original(instance, *args, **kwargs)
        with patch.object(FotoEntrada, "save", guardar), self.assertLogs("accesos.views", level="ERROR"):
            response = self.client.post(self.url, {**self.datos, "fotos": [self.foto(), self.foto()]})
        self.assertContains(response, "No se pudo guardar la entrada")
        self.assertFalse(RegistroVehicular.objects.exists())
        self.assertFalse(FotoEntrada.objects.exists())
        self.assertFalse(any(p.is_file() for p in Path(self.folder.name).rglob('*')))

    def test_permisos_para_galeria_y_archivo(self):
        self.client.post(self.url, {**self.datos, "fotos": [self.foto()]})
        foto = FotoEntrada.objects.get()
        urls = [reverse("fotos_entrada", args=[foto.registro_id]), reverse("foto_entrada_archivo", args=[foto.pk])]
        for rol in ("GUARDIA", "ADMINISTRADOR", "RESIDENTE", "TESORERO"):
            user = User.objects.create_user("otro-" + rol, rol=rol)
            UsuarioColonia.objects.create(usuario=user, colonia=self.otra if rol in ("GUARDIA", "ADMINISTRADOR") else self.colonia)
            self.client.force_login(user)
            for url in urls:
                self.assertEqual(self.client.get(url).status_code, 404 if rol in ("GUARDIA", "ADMINISTRADOR") else 403)
        self.client.logout()
        for url in urls:
            self.assertEqual(self.client.get(url).status_code, 302)

    def test_csrf_se_mantiene_y_boton_de_camara(self):
        c = Client(enforce_csrf_checks=True)
        c.force_login(self.guardia)
        self.assertEqual(c.post(self.url, {**self.datos, "fotos": [self.foto()]}).status_code, 403)
        response = self.client.get(self.url)
        self.assertContains(response, 'enctype="multipart/form-data"')
        self.assertContains(response, 'capture="environment"')
        self.assertContains(response, 'Tomar foto')
