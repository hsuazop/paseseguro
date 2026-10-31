from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from core.models import TimeStampedModel


class Responsable(TimeStampedModel):
    nombre_completo = models.CharField(max_length=180)
    identidad = models.CharField(max_length=20, unique=True)
    telefono = models.CharField(max_length=30, blank=True)
    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="responsable",
    )
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="responsables_creados",
    )
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ("nombre_completo",)

    def save(self, *args, **kwargs):
        self.identidad = self.identidad.strip()
        super().save(*args, **kwargs)

    def clean(self):
        if self.usuario_id and self.usuario.identidad and self.usuario.identidad != self.identidad:
            raise ValidationError({"usuario": "La identidad del usuario no coincide con la del responsable."})

    def __str__(self):
        return self.nombre_completo


class CasaResponsable(TimeStampedModel):
    casa = models.ForeignKey("colonias.Casa", on_delete=models.PROTECT, related_name="historial_responsables")
    responsable = models.ForeignKey(Responsable, on_delete=models.PROTECT, related_name="historial_casas")
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField(null=True, blank=True)
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ("-fecha_inicio", "-id")
        constraints = [
            models.UniqueConstraint(
                fields=("casa",),
                condition=Q(activo=True),
                name="un_responsable_activo_por_casa",
            ),
        ]

    def clean(self):
        if self.fecha_fin and self.fecha_fin < self.fecha_inicio:
            raise ValidationError({"fecha_fin": "La fecha final no puede ser anterior a la fecha inicial."})
        if self.activo and self.fecha_fin:
            raise ValidationError("Un historial activo no puede tener fecha final.")

    def __str__(self):
        return f"{self.casa} - {self.responsable}"
