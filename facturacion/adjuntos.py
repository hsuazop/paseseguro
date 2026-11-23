from pathlib import Path
from uuid import uuid4

from django.core.exceptions import ValidationError
from PIL import Image


def validar_adjunto(archivo):
    if archivo.size > 8 * 1024 * 1024:
        raise ValidationError("El comprobante no puede superar 8 MB.")
    extension = Path(archivo.name).suffix.lower()
    try:
        if extension == ".pdf":
            if archivo.read(5) != b"%PDF-":
                raise ValidationError("Adjunta un PDF válido.")
        else:
            formatos = {".png": "PNG", ".jpg": "JPEG", ".jpeg": "JPEG", ".webp": "WEBP"}
            with Image.open(archivo) as imagen:
                if imagen.format != formatos.get(extension):
                    raise ValidationError("El formato del archivo no coincide con su extensión.")
                imagen.verify()
    except (OSError, ValueError, SyntaxError, Image.DecompressionBombError):
        raise ValidationError("No se pudo leer la imagen del comprobante.")
    finally:
        archivo.seek(0)
    archivo.name = f"{uuid4().hex}{extension}"
    return archivo
