import base64
import os
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = 'Crea una clave VAPID fuera del repositorio; imprime únicamente la pública.'
    def add_arguments(self, parser):
        parser.add_argument('--archivo', required=True)
    def handle(self, *args, **options):
        path=Path(options['archivo']).resolve()
        if path.exists():
            raise CommandError('Ya existe. No sobrescribir: cambiar claves invalida suscripciones.')
        key=ec.generate_private_key(ec.SECP256R1())
        data=key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption())
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'wb') as handle: handle.write(data)
        public=key.public_key().public_bytes(serialization.Encoding.X962,serialization.PublicFormat.UncompressedPoint)
        self.stdout.write(base64.urlsafe_b64encode(public).decode().rstrip('='))
