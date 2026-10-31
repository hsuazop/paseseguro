from django.contrib.auth.models import AbstractUser
from django.db import models

from core.models import TimeStampedModel


class User(AbstractUser):
    class Rol(models.TextChoices):
        ADMINISTRADOR = "ADMINISTRADOR", "Administrador"
        GUARDIA = "GUARDIA", "Guardia"
        RESIDENTE = "RESIDENTE", "Usuario residente"

    identidad = models.CharField(max_length=20, unique=True, null=True, blank=True)
    rol = models.CharField(max_length=20, choices=Rol.choices, default=Rol.RESIDENTE)
    debe_cambiar_password = models.BooleanField(default=False)

    class Meta:
        verbose_name = "usuario"
        verbose_name_plural = "usuarios"

    def save(self, *args, **kwargs):
        if self.is_superuser:
            self.rol = self.Rol.ADMINISTRADOR
        self.identidad = self.identidad.strip() if self.identidad else None
        super().save(*args, **kwargs)

    @property
    def nombre_completo(self):
        return self.get_full_name() or self.username

    @property
    def es_superadmin(self):
        return self.is_superuser


class UsuarioColonia(TimeStampedModel):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE, related_name="asignaciones_colonia")
    colonia = models.ForeignKey("colonias.Colonia", on_delete=models.CASCADE, related_name="usuarios_asignados")
    activa = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("usuario", "colonia"), name="usuario_colonia_unica"),
        ]
        verbose_name = "asignacion de colonia"
        verbose_name_plural = "asignaciones de colonias"

    def __str__(self):
        return f"{self.usuario} - {self.colonia}"
