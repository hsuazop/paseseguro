from django.core.exceptions import ValidationError
from django.db import models

from core.models import TimeStampedModel


class Colonia(TimeStampedModel):
    nombre = models.CharField(max_length=160, unique=True)
    descripcion = models.TextField(blank=True)
    direccion = models.CharField(max_length=255, blank=True)
    telefono = models.CharField(max_length=30, blank=True)
    activa = models.BooleanField(default=True)

    class Meta:
        ordering = ("nombre",)

    def __str__(self):
        return self.nombre


class Casa(TimeStampedModel):
    colonia = models.ForeignKey(Colonia, on_delete=models.PROTECT, related_name="casas")
    codigo = models.CharField(max_length=40)
    numero = models.CharField(max_length=40)
    bloque = models.CharField(max_length=40, blank=True)
    calle = models.CharField(max_length=100, blank=True)
    referencia = models.CharField(max_length=255, blank=True)
    responsable_actual = models.ForeignKey(
        "residentes.Responsable",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="casas_actuales",
    )
    activa = models.BooleanField(default=True)

    class Meta:
        ordering = ("colonia__nombre", "codigo")
        constraints = [
            models.UniqueConstraint(fields=("colonia", "codigo"), name="casa_codigo_unico_colonia"),
        ]

    def clean(self):
        if self.responsable_actual_id and not self.activa:
            raise ValidationError("Una casa inactiva no debe tener un responsable actual activo.")

    def __str__(self):
        return f"{self.colonia} - Casa {self.codigo}"
