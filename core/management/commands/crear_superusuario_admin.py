import sys

from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.models import registrar_auditoria


class Command(BaseCommand):
    help = "Crea un superusuario de Django recibiendo la contraseña por entrada estándar."

    def add_arguments(self, parser):
        parser.add_argument('--username', required=True)

    @transaction.atomic
    def handle(self, *args, **options):
        password = sys.stdin.readline().rstrip('\r\n')
        if not password:
            raise CommandError('Debe proporcionar la contraseña por entrada estándar.')
        User = get_user_model()
        username = options['username']
        existing = User.objects.select_for_update().filter(username=username).first()
        if existing:
            if not (existing.is_superuser and existing.is_staff and existing.is_active
                    and not existing.debe_cambiar_password and existing.check_password(password)):
                raise CommandError('El nombre de usuario ya existe. No se modificó esa cuenta.')
            self.stdout.write(f'Superusuario {username} verificado; no fue necesario modificarlo.')
            return
        validate_password(password, User(username=username))
        user = User.objects.create_superuser(username=username, password=password, debe_cambiar_password=False)
        registrar_auditoria(usuario=user, accion='CREACION_SUPERUSUARIO', objeto=user,
                            descripcion='Superusuario de administración de Django creado.')
        self.stdout.write(self.style.SUCCESS(f'Superusuario {username} creado correctamente.'))
