from datetime import date
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from colonias.models import Casa, Colonia
from facturacion.models import ComprobantePago, CuotaMensual
from residentes.models import Responsable


class ComprobantePortalTests(TestCase):
    def setUp(self):
        self.colonia = Colonia.objects.create(nombre="Colonia Comprobantes")
        self.usuario = User.objects.create_user(
            username="0303000000001",
            identidad="0303000000001",
            password="Clave2026!",
            rol=User.Rol.RESIDENTE,
        )
        self.responsable = Responsable.objects.create(
            nombre_completo="Residente Comprobante",
            identidad="0303000000001",
            usuario=self.usuario,
        )
        self.casa = Casa.objects.create(
            colonia=self.colonia,
            codigo="P1",
            numero="1",
            responsable_actual=self.responsable,
        )
        self.cuota = CuotaMensual.objects.create(
            casa=self.casa,
            responsable=self.responsable,
            colonia=self.colonia,
            anio=2026,
            mes=10,
            monto_original=Decimal("500.00"),
            monto_pagado=Decimal("0.00"),
            saldo=Decimal("500.00"),
        )

    def test_envio_comprobante_no_modifica_saldo_financiero(self):
        self.client.force_login(self.usuario)
        archivo = SimpleUploadedFile("comprobante.pdf", b"contenido-de-prueba", content_type="application/pdf")
        response = self.client.post(
            reverse("comprobante_enviar", kwargs={"casa_id": self.casa.pk}),
            {
                "cuota_id": [self.cuota.pk],
                "fecha_pago": date(2026, 10, 31),
                "monto": "500.00",
                "metodo_pago": "TRANSFERENCIA",
                "referencia": "ABC123",
                "archivo": archivo,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(ComprobantePago.objects.count(), 1)
        self.cuota.refresh_from_db()
        self.assertEqual(self.cuota.saldo, Decimal("500.00"))
        self.assertEqual(self.cuota.monto_pagado, Decimal("0.00"))

