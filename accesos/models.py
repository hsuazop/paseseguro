from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from core.models import TimeStampedModel
from .fotos import almacenamiento_fotos_entrada, ruta_foto_entrada


class VehiculoColonia(TimeStampedModel):
    """Independent census: the only relationship is the residential community."""
    colonia = models.ForeignKey('colonias.Colonia', on_delete=models.PROTECT, related_name='padron_vehicular')
    placa = models.CharField(max_length=80, blank=True, db_index=True)
    propietario = models.CharField('nombre del propietario', max_length=250, blank=True)
    telefono = models.CharField('teléfono', max_length=150, blank=True)
    marca_modelo = models.CharField('marca / modelo', max_length=250, blank=True)
    color = models.CharField(max_length=100, blank=True)
    direccion = models.TextField('dirección / apartamento', blank=True)
    observaciones = models.TextField(blank=True)
    revisar = models.BooleanField('pendiente de revisar', default=False)
    activo = models.BooleanField(default=True)
    origen = models.JSONField(default=dict, blank=True, editable=False)
    clave_importacion = models.CharField(max_length=64, blank=True, editable=False)

    class Meta:
        ordering = ('placa', 'propietario', 'pk')
        verbose_name = 'vehículo de residencial'
        verbose_name_plural = 'padrón vehicular de residenciales'
        constraints = [models.UniqueConstraint(fields=('colonia', 'clave_importacion'), condition=~models.Q(clave_importacion=''), name='vehiculo_colonia_origen_unico')]

    def clean(self):
        self.placa = ''.join(self.placa.upper().split())
        if not any((self.placa, self.propietario.strip(), self.marca_modelo.strip())):
            raise ValidationError('Indica al menos placa, propietario o marca / modelo.')

    def save(self, *args, **kwargs):
        self.placa = ''.join(self.placa.upper().split())
        super().save(*args, **kwargs)

    def __str__(self):
        return f'{self.placa or "Sin placa"} · {self.propietario or self.marca_modelo}'


class Vehiculo(TimeStampedModel):
    class Tipo(models.TextChoices):
        AUTOMOVIL = "AUTOMOVIL", "Automóvil"
        MOTOCICLETA = "MOTOCICLETA", "Motocicleta"
        PICKUP = "PICKUP", "Pickup"
        OTRO = "OTRO", "Otro"

    responsable = models.ForeignKey("residentes.Responsable", on_delete=models.PROTECT, related_name="vehiculos")
    colonia = models.ForeignKey("colonias.Colonia", on_delete=models.PROTECT, related_name="vehiculos")
    casa = models.ForeignKey("colonias.Casa", on_delete=models.PROTECT, related_name="vehiculos")
    placa = models.CharField(max_length=20)
    tipo = models.CharField(max_length=15, choices=Tipo.choices, default=Tipo.AUTOMOVIL)
    marca = models.CharField(max_length=80, blank=True)
    modelo = models.CharField(max_length=80, blank=True)
    color = models.CharField(max_length=50, blank=True)
    descripcion = models.CharField(max_length=160, blank=True)
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ("placa",)
        constraints = [
            models.UniqueConstraint(fields=("colonia", "placa"), name="vehiculo_placa_unica_colonia"),
        ]

    def clean(self):
        self.placa = self.placa.strip().upper().replace(" ", "")
        if self.casa_id and self.casa.colonia_id != self.colonia_id:
            raise ValidationError("La residencia y el vehículo deben pertenecer a la misma colonia.")
        if self.casa_id and self.casa.responsable_actual_id != self.responsable_id:
            raise ValidationError("La residencia no corresponde a la persona propietaria del vehículo.")

    def save(self, *args, **kwargs):
        self.placa = self.placa.strip().upper().replace(" ", "")
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.placa} - {self.responsable}"


class RegistroVehicular(TimeStampedModel):
    class TipoAcceso(models.TextChoices):
        RESIDENTE = "RESIDENTE", "Residente"
        VISITANTE = "VISITANTE", "Visitante"
        PROVEEDOR = "PROVEEDOR", "Proveedor o servicio"

    colonia = models.ForeignKey("colonias.Colonia", on_delete=models.PROTECT, related_name="registros_vehiculares")
    vehiculo = models.ForeignKey(Vehiculo, on_delete=models.PROTECT, null=True, blank=True, related_name="accesos")
    placa = models.CharField(max_length=20)
    tipo_acceso = models.CharField(max_length=15, choices=TipoAcceso.choices)
    casa_destino = models.ForeignKey(
        "colonias.Casa",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="accesos_vehiculares",
    )
    responsable_destino = models.ForeignKey(
        "residentes.Responsable",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="visitas_vehiculares",
    )
    conductor = models.CharField(max_length=180, blank=True)
    identidad_conductor = models.CharField(max_length=30, blank=True)
    personas = models.PositiveSmallIntegerField(default=1, validators=[MinValueValidator(1)])
    fecha_entrada = models.DateTimeField(default=timezone.now)
    fecha_salida = models.DateTimeField(null=True, blank=True)
    guardia_entrada = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="ingresos_vehiculares_registrados",
    )
    guardia_salida = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="salidas_vehiculares_registradas",
    )
    observaciones = models.TextField(blank=True)

    class Meta:
        ordering = ("-fecha_entrada", "-id")
        verbose_name = "registro vehicular"
        verbose_name_plural = "registros vehiculares"

    def clean(self):
        self.placa = self.placa.strip().upper().replace(" ", "")
        if self.casa_destino_id and self.casa_destino.colonia_id != self.colonia_id:
            raise ValidationError("La residencia destino no pertenece a la colonia seleccionada.")
        if self.fecha_salida and self.fecha_salida < self.fecha_entrada:
            raise ValidationError("La salida no puede ser anterior a la entrada.")

    def save(self, *args, **kwargs):
        self.placa = self.placa.strip().upper().replace(" ", "")
        super().save(*args, **kwargs)

    @property
    def dentro(self):
        return self.fecha_salida is None

    def __str__(self):
        return f"{self.placa} - {self.fecha_entrada:%d/%m/%Y %H:%M}"


class FotoEntrada(TimeStampedModel):
    registro = models.ForeignKey(RegistroVehicular, on_delete=models.PROTECT, related_name="fotos")
    archivo = models.FileField(upload_to=ruta_foto_entrada, storage=almacenamiento_fotos_entrada)

    class Meta:
        ordering = ("created_at", "pk")
        verbose_name = "foto de entrada"
        verbose_name_plural = "fotos de entradas"

    def __str__(self):
        return f"Foto de entrada #{self.registro_id}"

