from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.utils import timezone


MAX_FOTOS_ENTRADA = 8
MAX_BYTES_FOTO = 8 * 1024 * 1024


def almacenamiento_fotos_entrada():
    return FileSystemStorage(location=settings.PRIVATE_MEDIA_ROOT,
        file_permissions_mode=0o600, directory_permissions_mode=0o700)


def ruta_foto_entrada(instance, filename):
    return f"entradas/{timezone.localdate():%Y/%m}/{uuid4().hex}{Path(filename).suffix.lower()}"
