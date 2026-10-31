from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from core.models import TimeStampedModel


class SolicitudMensaje(TimeStampedModel):
    class Tipo(models.TextChoices):
        SOLICITUD = "SOLICITUD", "Solicitud"
        MENSAJE = "MENSAJE", "Mensaje"
        ALERTA = "ALERTA", "Alerta"

    class Visibilidad(models.TextChoices):
        PRIVADA = "PRIVADA", "Privado"
        PUBLICA = "PUBLICA", "Público"

    class Estado(models.TextChoices):
        NUEVO = "NUEVO", "Nuevo"
        EN_PROCESO = "EN_PROCESO", "En proceso"
        RESUELTO = "RESUELTO", "Resuelto"

    colonia = models.ForeignKey("colonias.Colonia", on_delete=models.PROTECT, related_name="solicitudes")
    casa = models.ForeignKey("colonias.Casa", on_delete=models.PROTECT, related_name="solicitudes")
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="solicitudes")
    tipo = models.CharField(max_length=15, choices=Tipo.choices, default=Tipo.SOLICITUD)
    visibilidad = models.CharField(max_length=10, choices=Visibilidad.choices, default=Visibilidad.PRIVADA)
    asunto = models.CharField(max_length=160)
    mensaje = models.TextField()
    adjunto = models.FileField(upload_to="comunidad/solicitudes/%Y/%m/", blank=True)
    estado = models.CharField(max_length=15, choices=Estado.choices, default=Estado.NUEVO)
    respuesta = models.TextField(blank=True)
    respondido_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="solicitudes_respondidas",
    )
    respondido_en = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return self.asunto


class AlertaSOS(TimeStampedModel):
    class Estado(models.TextChoices):
        NUEVA = "NUEVA", "Nueva"
        ATENDIENDO = "ATENDIENDO", "Atendiendo"
        CERRADA = "CERRADA", "Cerrada"

    colonia = models.ForeignKey("colonias.Colonia", on_delete=models.PROTECT, related_name="alertas_sos")
    casa = models.ForeignKey("colonias.Casa", on_delete=models.PROTECT, related_name="alertas_sos")
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="alertas_sos")
    mensaje = models.TextField()
    adjunto = models.FileField(upload_to="comunidad/sos/%Y/%m/", blank=True)
    estado = models.CharField(max_length=12, choices=Estado.choices, default=Estado.NUEVA)

    class Meta:
        ordering = ("-created_at",)
        verbose_name = "alerta SOS"
        verbose_name_plural = "alertas SOS"

    def __str__(self):
        return f"SOS {self.casa} - {self.created_at:%d/%m/%Y %H:%M}"


class Comunicado(TimeStampedModel):
    colonia = models.ForeignKey("colonias.Colonia", on_delete=models.PROTECT, related_name="comunicados")
    titulo = models.CharField(max_length=180)
    contenido = models.TextField()
    imagen = models.FileField(upload_to="comunidad/comunicados/%Y/%m/", blank=True)
    adjunto = models.FileField(upload_to="comunidad/documentos/%Y/%m/", blank=True)
    publicado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="comunicados")
    publicado_en = models.DateTimeField(default=timezone.now)
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ("-publicado_en",)

    def __str__(self):
        return self.titulo


class Clasificado(TimeStampedModel):
    colonia = models.ForeignKey("colonias.Colonia", on_delete=models.PROTECT, related_name="clasificados")
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="clasificados")
    titulo = models.CharField(max_length=160)
    descripcion = models.TextField()
    precio = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    telefono = models.CharField(max_length=30, blank=True)
    imagen = models.FileField(upload_to="comunidad/clasificados/%Y/%m/", blank=True)
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ("-created_at",)

    def __str__(self):
        return self.titulo


class DirectorioEntrada(TimeStampedModel):
    colonia = models.ForeignKey("colonias.Colonia", on_delete=models.PROTECT, related_name="directorio")
    nombre = models.CharField(max_length=160)
    categoria = models.CharField(max_length=100, blank=True)
    telefono = models.CharField(max_length=30)
    descripcion = models.CharField(max_length=255, blank=True)
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ("categoria", "nombre")
        verbose_name = "entrada de directorio"
        verbose_name_plural = "directorio"

    def __str__(self):
        return self.nombre


class DocumentoComunidad(TimeStampedModel):
    colonia = models.ForeignKey("colonias.Colonia", on_delete=models.PROTECT, related_name="documentos")
    titulo = models.CharField(max_length=180)
    descripcion = models.CharField(max_length=255, blank=True)
    archivo = models.FileField(upload_to="comunidad/biblioteca/%Y/%m/")
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ("titulo",)
        verbose_name = "documento de comunidad"
        verbose_name_plural = "documentos de comunidad"

    def __str__(self):
        return self.titulo

