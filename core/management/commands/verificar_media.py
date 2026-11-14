import tempfile
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db.models import FileField


class Command(BaseCommand):
    help = "Verifica la carpeta de archivos subidos y muestra sus rutas por año y mes."

    def handle(self, *args, **options):
        root = Path(settings.MEDIA_ROOT)
        if not root.is_absolute():
            raise CommandError("DJANGO_MEDIA_ROOT debe ser una ruta absoluta.")
        if root.resolve() == Path(settings.STATIC_ROOT).resolve():
            raise CommandError("MEDIA_ROOT y STATIC_ROOT deben ser carpetas diferentes.")
        try:
            root.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix=".verificar-media-", dir=root) as folder:
                probe = Path(folder) / "prueba.txt"
                probe.write_text("PaseSeguro", encoding="utf-8")
                if probe.read_text(encoding="utf-8") != "PaseSeguro":
                    raise CommandError("No se pudo leer el archivo de prueba.")
        except OSError as exc:
            raise CommandError(f"No se puede escribir o leer MEDIA_ROOT: {exc}") from exc
        self.stdout.write(f"MEDIA_ROOT: {root}")
        self.stdout.write(f"MEDIA_URL: {settings.MEDIA_URL}")
        for model in apps.get_models():
            if model._meta.app_label not in {'facturacion', 'comunidad', 'reservas'}:
                continue
            for field in model._meta.fields:
                if isinstance(field, FileField):
                    self.stdout.write(f"  {model._meta.label}.{field.name}: {field.upload_to}")
        self.stdout.write(self.style.SUCCESS("Lectura y escritura correctas. La ruta pública /media/ debe verificarse también en Opalstack."))
