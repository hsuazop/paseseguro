from django.conf import settings
from django.db import models


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class AuditLog(models.Model):
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="auditorias",
    )
    accion = models.CharField(max_length=60)
    modelo = models.CharField(max_length=120)
    object_id = models.CharField(max_length=64, blank=True)
    descripcion = models.TextField()
    datos_anteriores = models.JSONField(null=True, blank=True)
    datos_nuevos = models.JSONField(null=True, blank=True)
    fecha = models.DateTimeField(auto_now_add=True)
    ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ("-fecha",)
        verbose_name = "registro de auditoria"
        verbose_name_plural = "registros de auditoria"

    def __str__(self):
        return f"{self.accion}: {self.modelo} {self.object_id}".strip()


def registrar_auditoria(*, usuario, accion, objeto, descripcion, anteriores=None, nuevos=None, ip=None):
    return AuditLog.objects.create(
        usuario=usuario if getattr(usuario, "is_authenticated", False) else None,
        accion=accion,
        modelo=objeto._meta.label,
        object_id=str(objeto.pk or ""),
        descripcion=descripcion,
        datos_anteriores=anteriores,
        datos_nuevos=nuevos,
        ip=ip,
    )
