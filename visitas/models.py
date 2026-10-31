import secrets
import uuid
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from core.models import TimeStampedModel


def crear_clave_acceso():
    return secrets.token_hex(4).upper()


class Visita(TimeStampedModel):
    class Tipo(models.TextChoices):
        VISITA = "VISITA", "Visita"
        SERVICIO = "SERVICIO", "Servicio o proveedor"

    class Temporalidad(models.TextChoices):
        UNICA = "UNICA", "Una sola vez"
        MULTIPLE = "MULTIPLE", "Varias entradas"

    casa = models.ForeignKey("colonias.Casa", on_delete=models.PROTECT, related_name="visitas")
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="visitas_creadas",
    )
    tipo = models.CharField(max_length=15, choices=Tipo.choices, default=Tipo.VISITA)
    temporalidad = models.CharField(max_length=15, choices=Temporalidad.choices, default=Temporalidad.UNICA)
    nombre_visitante = models.CharField(max_length=180)
    identidad_visitante = models.CharField(max_length=30, blank=True)
    fecha_inicio = models.DateTimeField()
    fecha_fin = models.DateTimeField(null=True, blank=True)
    max_usos = models.PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1)])
    max_personas = models.PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1)])
    usos_actuales = models.PositiveSmallIntegerField(default=0)
    clave_acceso = models.CharField(max_length=16, unique=True, default=crear_clave_acceso, editable=False)
    token_publico = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    activa = models.BooleanField(default=True)

    class Meta:
        ordering = ("-fecha_inicio", "-id")
        verbose_name = "visita programada"
        verbose_name_plural = "visitas programadas"

    def clean(self):
        if self.fecha_fin and self.fecha_fin < self.fecha_inicio:
            raise ValidationError({"fecha_fin": "La fecha final no puede ser anterior a la fecha inicial."})
        if self.temporalidad == self.Temporalidad.UNICA and self.max_usos != 1:
            raise ValidationError({"max_usos": "Una visita de una sola vez debe permitir un único uso."})

    @property
    def vigente(self):
        ahora = timezone.now()
        fin = self.fecha_fin or self.fecha_inicio + timedelta(days=1)
        return self.activa and self.usos_actuales < self.max_usos and self.fecha_inicio <= ahora <= fin

    def __str__(self):
        return f"{self.nombre_visitante} - {self.casa}"


class RegistroAcceso(TimeStampedModel):
    visita = models.ForeignKey(Visita, on_delete=models.PROTECT, related_name="accesos")
    registrado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="accesos_registrados",
    )
    personas = models.PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1)])
    observacion = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ("-created_at",)

