from io import BytesIO
from tempfile import TemporaryDirectory

from PIL import Image
from django.core.files.storage import FileSystemStorage
from django.core.files.uploadedfile import SimpleUploadedFile

from .models import FotoEntrada


def foto_prueba():
    stream = BytesIO()
    Image.new("RGB", (20, 20), "blue").save(stream, format="JPEG")
    return SimpleUploadedFile("foto.jpg", stream.getvalue(), content_type="image/jpeg")


def aislar_fotos(test):
    folder = TemporaryDirectory()
    test.addCleanup(folder.cleanup)
    field = FotoEntrada._meta.get_field("archivo")
    test.addCleanup(setattr, field, "storage", field.storage)
    field.storage = FileSystemStorage(location=folder.name)
