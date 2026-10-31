import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator, MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone

from core.models import TimeStampedModel


class TarifaColonia(TimeStampedModel):
    colonia = models.ForeignKey("colonias.Colonia", on_delete=models.PROTECT, related_name="tarifas")
    monto = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField(null=True, blank=True)
    activa = models.BooleanField(default=True)

    class Meta:
        ordering = ("-fecha_inicio",)

    def clean(self):
        if self.fecha_fin and self.fecha_fin < self.fecha_inicio:
            raise ValidationError({"fecha_fin": "La fecha final no puede ser anterior a la fecha inicial."})
        if self.activa and self.colonia_id:
            fin = self.fecha_fin or timezone.datetime.max.date()
            solapada = TarifaColonia.objects.filter(colonia_id=self.colonia_id, activa=True).exclude(pk=self.pk).filter(
                fecha_inicio__lte=fin
            ).filter(Q(fecha_fin__isnull=True) | Q(fecha_fin__gte=self.fecha_inicio))
            if solapada.exists():
                raise ValidationError("Ya existe una tarifa activa que se cruza con este periodo.")

    def __str__(self):
        return f"{self.colonia}: L {self.monto} desde {self.fecha_inicio:%d/%m/%Y}"


class TarifaEspecialCasa(TimeStampedModel):
    class Tipo(models.TextChoices):
        MONTO_FIJO = "MONTO_FIJO", "Monto fijo"
        PORCENTAJE = "PORCENTAJE", "Porcentaje"

    casa = models.ForeignKey("colonias.Casa", on_delete=models.PROTECT, related_name="tarifas_especiales")
    tipo = models.CharField(max_length=20, choices=Tipo.choices)
    monto = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    porcentaje = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.01")), MaxValueValidator(Decimal("100.00"))],
    )
    motivo = models.CharField(max_length=255)
    fecha_inicio = models.DateField()
    fecha_fin = models.DateField(null=True, blank=True)
    activa = models.BooleanField(default=True)
    usuario_que_autoriza = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="tarifas_especiales_autorizadas",
    )

    class Meta:
        ordering = ("-fecha_inicio",)

    def clean(self):
        if self.fecha_fin and self.fecha_fin < self.fecha_inicio:
            raise ValidationError({"fecha_fin": "La fecha final no puede ser anterior a la fecha inicial."})
        if self.tipo == self.Tipo.MONTO_FIJO:
            if not self.monto or self.monto <= 0:
                raise ValidationError({"monto": "Ingrese un monto fijo mayor que cero."})
            if self.porcentaje is not None:
                raise ValidationError({"porcentaje": "No corresponde indicar porcentaje para un monto fijo."})
        elif self.tipo == self.Tipo.PORCENTAJE:
            if not self.porcentaje or self.porcentaje <= 0 or self.porcentaje > 100:
                raise ValidationError({"porcentaje": "Ingrese un porcentaje entre 0 y 100."})
            if self.monto is not None:
                raise ValidationError({"monto": "No corresponde indicar monto para una tarifa porcentual."})
        if self.activa and self.casa_id:
            fin = self.fecha_fin or timezone.datetime.max.date()
            solapada = TarifaEspecialCasa.objects.filter(casa_id=self.casa_id, activa=True).exclude(pk=self.pk).filter(
                fecha_inicio__lte=fin
            ).filter(Q(fecha_fin__isnull=True) | Q(fecha_fin__gte=self.fecha_inicio))
            if solapada.exists():
                raise ValidationError("Ya existe una tarifa especial activa que se cruza con este periodo.")

    def __str__(self):
        return f"{self.casa}: {self.get_tipo_display()}"


class CuotaMensual(TimeStampedModel):
    class Estado(models.TextChoices):
        PENDIENTE = "PENDIENTE", "Pendiente"
        PARCIAL = "PARCIAL", "Parcial"
        PAGADA = "PAGADA", "Pagada"
        ANULADA = "ANULADA", "Anulada"

    MESES = (
        (1, "Enero"), (2, "Febrero"), (3, "Marzo"), (4, "Abril"),
        (5, "Mayo"), (6, "Junio"), (7, "Julio"), (8, "Agosto"),
        (9, "Septiembre"), (10, "Octubre"), (11, "Noviembre"), (12, "Diciembre"),
    )

    casa = models.ForeignKey("colonias.Casa", on_delete=models.PROTECT, related_name="cuotas")
    responsable = models.ForeignKey(
        "residentes.Responsable",
        on_delete=models.PROTECT,
        related_name="cuotas",
    )
    colonia = models.ForeignKey(
        "colonias.Colonia",
        on_delete=models.PROTECT,
        related_name="cuotas_persona",
    )
    anio = models.PositiveSmallIntegerField("año")
    mes = models.PositiveSmallIntegerField(choices=MESES)
    monto_original = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    monto_pagado = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    saldo = models.DecimalField(max_digits=12, decimal_places=2)
    estado = models.CharField(max_length=12, choices=Estado.choices, default=Estado.PENDIENTE)
    fecha_vencimiento = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ("anio", "mes")
        constraints = [
            models.UniqueConstraint(
                fields=("responsable", "colonia", "anio", "mes"),
                name="cuota_unica_persona_colonia_periodo",
            ),
            models.CheckConstraint(condition=Q(mes__gte=1, mes__lte=12), name="mes_cuota_valido"),
            models.CheckConstraint(condition=Q(monto_original__gt=0), name="monto_cuota_positivo"),
            models.CheckConstraint(condition=Q(monto_pagado__gte=0), name="cuota_pagado_no_negativo"),
            models.CheckConstraint(condition=Q(saldo__gte=0), name="cuota_saldo_no_negativo"),
        ]

    @property
    def periodo(self):
        return f"{self.get_mes_display()} {self.anio}"

    def __str__(self):
        return f"{self.casa} - {self.periodo}"


class ReciboSecuencia(models.Model):
    anio = models.PositiveSmallIntegerField("año", unique=True)
    ultimo_numero = models.PositiveIntegerField(default=0)


class Pago(TimeStampedModel):
    class Metodo(models.TextChoices):
        EFECTIVO = "EFECTIVO", "Efectivo"
        TRANSFERENCIA = "TRANSFERENCIA", "Transferencia"
        DEPOSITO = "DEPOSITO", "Deposito"
        OTRO = "OTRO", "Otro"

    numero_recibo = models.CharField(max_length=24, unique=True)
    token_publico = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    casa = models.ForeignKey("colonias.Casa", on_delete=models.PROTECT, related_name="pagos")
    colonia = models.ForeignKey(
        "colonias.Colonia",
        on_delete=models.PROTECT,
        related_name="pagos",
    )
    responsable = models.ForeignKey("residentes.Responsable", on_delete=models.PROTECT, related_name="pagos")
    fecha_pago = models.DateField(default=timezone.localdate)
    monto_total = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    metodo_pago = models.CharField(max_length=20, choices=Metodo.choices)
    referencia = models.CharField(max_length=120, blank=True)
    observaciones = models.TextField(blank=True)
    usuario_que_registra = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="pagos_registrados",
    )
    anulado = models.BooleanField(default=False)
    motivo_anulacion = models.TextField(blank=True)
    usuario_que_anula = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="pagos_anulados",
    )
    fecha_anulacion = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-fecha_pago", "-id")
        constraints = [models.CheckConstraint(condition=Q(monto_total__gt=0), name="pago_monto_positivo")]

    def __str__(self):
        return self.numero_recibo


class AplicacionPago(TimeStampedModel):
    pago = models.ForeignKey(Pago, on_delete=models.PROTECT, related_name="aplicaciones")
    cuota_mensual = models.ForeignKey(CuotaMensual, on_delete=models.PROTECT, related_name="aplicaciones")
    monto_aplicado = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )

    class Meta:
        ordering = ("cuota_mensual__anio", "cuota_mensual__mes")
        constraints = [
            models.UniqueConstraint(fields=("pago", "cuota_mensual"), name="aplicacion_unica_pago_cuota"),
            models.CheckConstraint(condition=Q(monto_aplicado__gt=0), name="aplicacion_monto_positivo"),
        ]

    def clean(self):
        if self.pago_id and self.cuota_mensual_id:
            if self.pago.responsable_id != self.cuota_mensual.responsable_id:
                raise ValidationError("El pago y la cuota deben pertenecer a la misma persona.")
            if self.pago.colonia_id != self.cuota_mensual.colonia_id:
                raise ValidationError("El pago y la cuota deben pertenecer a la misma colonia.")

    def __str__(self):
        return f"{self.pago} -> {self.cuota_mensual.periodo}"


class CuentaPagoColonia(TimeStampedModel):
    colonia = models.ForeignKey("colonias.Colonia", on_delete=models.PROTECT, related_name="cuentas_pago")
    banco = models.CharField(max_length=120)
    tipo_cuenta = models.CharField(max_length=80, blank=True)
    numero_cuenta = models.CharField(max_length=80)
    titular = models.CharField(max_length=180)
    identidad_titular = models.CharField(max_length=30, blank=True)
    instrucciones = models.TextField(blank=True)
    activa = models.BooleanField(default=True)

    class Meta:
        ordering = ("banco", "numero_cuenta")
        verbose_name = "cuenta para pagos"
        verbose_name_plural = "cuentas para pagos"

    def __str__(self):
        return f"{self.banco} - {self.numero_cuenta}"


class ComprobantePago(TimeStampedModel):
    class Estado(models.TextChoices):
        PENDIENTE = "PENDIENTE", "Pendiente de revisión"
        APROBADO = "APROBADO", "Aprobado"
        RECHAZADO = "RECHAZADO", "Rechazado"

    casa = models.ForeignKey("colonias.Casa", on_delete=models.PROTECT, related_name="comprobantes_pago")
    colonia = models.ForeignKey(
        "colonias.Colonia",
        on_delete=models.PROTECT,
        related_name="comprobantes_pago",
    )
    responsable = models.ForeignKey(
        "residentes.Responsable",
        on_delete=models.PROTECT,
        related_name="comprobantes_pago",
    )
    enviado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="comprobantes_enviados",
    )
    fecha_pago = models.DateField(default=timezone.localdate)
    monto = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    metodo_pago = models.CharField(max_length=20, choices=Pago.Metodo.choices)
    referencia = models.CharField(max_length=120, blank=True)
    archivo = models.FileField(
        upload_to="comprobantes/%Y/%m/",
        validators=[FileExtensionValidator(("pdf", "jpg", "jpeg", "png", "webp"))],
    )
    comentario = models.TextField(blank=True)
    estado = models.CharField(max_length=12, choices=Estado.choices, default=Estado.PENDIENTE)
    comentario_revision = models.TextField(blank=True)
    revisado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="comprobantes_revisados",
    )
    revisado_en = models.DateTimeField(null=True, blank=True)
    pago = models.OneToOneField(
        Pago,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="comprobante_origen",
    )
    cuotas = models.ManyToManyField(CuotaMensual, through="ComprobanteCuota", related_name="comprobantes")

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "comprobante de pago"
        verbose_name_plural = "comprobantes de pago"

    def clean(self):
        if self.casa_id and self.responsable_id and self.casa.responsable_actual_id != self.responsable_id:
            raise ValidationError("El responsable no corresponde a la casa seleccionada.")
        if self.casa_id and self.colonia_id and self.casa.colonia_id != self.colonia_id:
            raise ValidationError("La residencia no corresponde a la colonia seleccionada.")

    def __str__(self):
        return f"Comprobante #{self.pk or 'nuevo'} - {self.casa}"


class ComprobanteCuota(models.Model):
    comprobante = models.ForeignKey(ComprobantePago, on_delete=models.CASCADE, related_name="conceptos")
    cuota = models.ForeignKey(CuotaMensual, on_delete=models.PROTECT, related_name="selecciones_comprobante")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("comprobante", "cuota"), name="comprobante_cuota_unica"),
        ]

    def clean(self):
        if self.comprobante_id and self.cuota_id:
            if self.comprobante.responsable_id != self.cuota.responsable_id:
                raise ValidationError("La cuota debe pertenecer a la misma persona.")
            if self.comprobante.colonia_id != self.cuota.colonia_id:
                raise ValidationError("La cuota debe pertenecer a la misma colonia.")
