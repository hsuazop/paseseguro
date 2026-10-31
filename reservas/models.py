from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

from core.models import TimeStampedModel


class AreaComun(TimeStampedModel):
    colonia = models.ForeignKey("colonias.Colonia", on_delete=models.PROTECT, related_name="areas_comunes")
    nombre = models.CharField(max_length=160)
    descripcion = models.TextField(blank=True)
    reglas = models.TextField(blank=True)
    capacidad = models.PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1)])
    costo = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    imagen = models.FileField(upload_to="reservas/areas/%Y/%m/", blank=True)
    requiere_aprobacion = models.BooleanField(default=True)
    activa = models.BooleanField(default=True)

    class Meta:
        ordering = ("nombre",)
        constraints = [
            models.UniqueConstraint(fields=("colonia", "nombre"), name="area_nombre_unico_colonia"),
        ]

    def __str__(self):
        return f"{self.nombre} - {self.colonia}"


class Reserva(TimeStampedModel):
    class Estado(models.TextChoices):
        PENDIENTE = "PENDIENTE", "Pendiente"
        APROBADA = "APROBADA", "Aprobada"
        RECHAZADA = "RECHAZADA", "Rechazada"
        CANCELADA = "CANCELADA", "Cancelada"

    area = models.ForeignKey(AreaComun, on_delete=models.PROTECT, related_name="reservas")
    casa = models.ForeignKey("colonias.Casa", on_delete=models.PROTECT, related_name="reservas")
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="reservas")
    fecha = models.DateField()
    hora_inicio = models.TimeField()
    hora_fin = models.TimeField()
    personas = models.PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1)])
    motivo = models.CharField(max_length=255, blank=True)
    estado = models.CharField(max_length=12, choices=Estado.choices, default=Estado.PENDIENTE)
    observacion_revision = models.TextField(blank=True)
    revisado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="reservas_revisadas",
    )

    class Meta:
        ordering = ("-fecha", "-hora_inicio")

    def clean(self):
        if self.hora_fin <= self.hora_inicio:
            raise ValidationError({"hora_fin": "La hora final debe ser posterior a la hora inicial."})
        if self.area_id and self.casa_id and self.area.colonia_id != self.casa.colonia_id:
            raise ValidationError("El área y la casa deben pertenecer a la misma colonia.")
        if self.area_id and self.personas and self.personas > self.area.capacidad:
            raise ValidationError({"personas": "La cantidad supera la capacidad del área."})
        if self.area_id and self.fecha and self.hora_inicio and self.hora_fin:
            ocupada = Reserva.objects.filter(
                area_id=self.area_id,
                fecha=self.fecha,
                estado__in=(self.Estado.PENDIENTE, self.Estado.APROBADA),
                hora_inicio__lt=self.hora_fin,
                hora_fin__gt=self.hora_inicio,
            ).exclude(pk=self.pk)
            if ocupada.exists():
                raise ValidationError("El área ya está reservada en ese horario.")

    def __str__(self):
        return f"{self.area.nombre} - {self.fecha:%d/%m/%Y}"

