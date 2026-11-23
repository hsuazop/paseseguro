from django.db import models


class DatosBancariosPago(models.Model):
    class Banco(models.TextChoices):
        BAC = "BAC", "BAC"
        FICOHSA = "FICOHSA", "Ficohsa"

    banco = models.CharField("Banco del pago", max_length=10, choices=Banco.choices, blank=True)
    numero_cuenta = models.CharField("Número de cuenta del pago", max_length=80, blank=True)

    class Meta:
        abstract = True
