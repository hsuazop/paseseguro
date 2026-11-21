from datetime import date
from decimal import Decimal

from django.test import Client, TestCase
from django.urls import reverse

from accounts.models import User, UsuarioColonia
from colonias.models import Casa, Colonia
from core.models import AuditLog
from residentes.models import Responsable
from .models import CuotaMensual, GastoMensual
from .services import anular_pago, registrar_pago


class GastosTests(TestCase):
    def setUp(self):
        self.colonia = Colonia.objects.create(nombre="Las Palmas")
        self.otra = Colonia.objects.create(nombre="Otra colonia")
        self.tesorero = User.objects.create_user("tesorero", rol="TESORERO")
        UsuarioColonia.objects.create(usuario=self.tesorero, colonia=self.colonia)
        self.persona = Responsable.objects.create(nombre_completo="Ana", identidad="123")
        self.casa = Casa.objects.create(colonia=self.colonia, codigo="001", responsable_actual=self.persona)
        self.client.force_login(self.tesorero)
        self.datos = {"tipo": "VIGILANCIA", "anio": 2026, "mes": 11, "monto": "400.25", "descripcion": "Turnos de noviembre"}

    def gasto(self, **datos):
        return GastoMensual.objects.create(colonia=self.colonia, registrado_por=self.tesorero, **{**self.datos, **datos})

    def cuota(self, mes):
        return CuotaMensual.objects.create(colonia=self.colonia, casa=self.casa, responsable=self.persona,
            anio=2026, mes=mes, monto_original=500, saldo=500)

    def test_registra_varios_gastos_y_fija_colonia_y_usuario(self):
        for tipo in ("VIGILANCIA", "PINTURA", "ALBANIL", "OTRO"):
            response = self.client.post(reverse("gasto_crear"), {**self.datos, "tipo": tipo, "colonia": self.otra.pk, "registrado_por": 999})
            self.assertEqual(response.status_code, 302)
        self.assertEqual(GastoMensual.objects.filter(colonia=self.colonia, registrado_por=self.tesorero).count(), 4)
        self.assertEqual(AuditLog.objects.filter(accion="CREAR_GASTO").count(), 4)
        response = self.client.get(reverse("gastos_lista"), {"anio": 2026, "mes": 11})
        self.assertEqual(response.context["total_gastos"], Decimal("1601.00"))
        self.assertEqual(response.context["page_obj"].paginator.count, 4)

    def test_valida_monto_periodo_tipo_y_descripcion(self):
        for campo, valor in (("monto", "0"), ("monto", "-1"), ("monto", "1.001"), ("mes", 13), ("anio", 2019),
                             ("anio", 2101), ("tipo", "INVALIDO"), ("descripcion", "   ")):
            with self.subTest(campo=campo, valor=valor):
                response = self.client.post(reverse("gasto_crear"), {**self.datos, campo: valor})
                self.assertEqual(response.status_code, 200)
                self.assertIn(campo, response.context["form"].errors)
        self.assertFalse(GastoMensual.objects.exists())

    def test_editar_conserva_colonia_y_autor_y_guarda_auditoria(self):
        gasto = self.gasto()
        response = self.client.post(reverse("gasto_editar", args=[gasto.pk]),
            {**self.datos, "monto": "300", "mes": 10, "colonia": self.otra.pk})
        self.assertEqual(response.status_code, 302)
        gasto.refresh_from_db()
        self.assertEqual(gasto.colonia, self.colonia)
        self.assertEqual(gasto.registrado_por, self.tesorero)
        self.assertEqual(gasto.monto, 300)
        audit = AuditLog.objects.get(accion="EDITAR_GASTO")
        self.assertEqual(audit.datos_anteriores["monto"], "400.25")
        self.assertEqual(audit.datos_nuevos["mes"], 10)

    def test_resumen_aplica_pagos_al_periodo_y_excluye_anulaciones(self):
        octubre, noviembre = self.cuota(10), self.cuota(11)
        pago = registrar_pago(casa=self.casa, responsable=self.persona, fecha_pago=date(2026, 12, 1),
            monto_total=700, metodo_pago="EFECTIVO", usuario=self.tesorero,
            aplicaciones=[{"cuota_id": octubre.pk, "monto": 500}, {"cuota_id": noviembre.pk, "monto": 200}])
        self.gasto()
        self.gasto(tipo="PINTURA", monto="20.50")
        self.gasto(mes=10, monto="100.00")
        self.gasto(anio=2025, monto="999.00")
        response = self.client.get(reverse("resumen_contable"), {"anio": 2026, "mes": 11})
        self.assertEqual(response.context["recaudado"], 200)
        self.assertEqual(response.context["gastos"], Decimal("420.75"))
        self.assertEqual(response.context["saldo"], Decimal("-220.75"))
        self.assertEqual(response.context["recaudado_anio"], 700)
        self.assertEqual(response.context["gastos_anio"], Decimal("520.75"))
        self.assertEqual(response.context["saldo_anio"], Decimal("179.25"))
        self.assertEqual(len(response.context["filas"]), 12)
        self.assertEqual(response.context["filas"][9]["saldo"], 400)
        self.assertEqual(len(response.context["detalle_gastos"]), 2)
        anular_pago(pago=pago, motivo="Prueba", usuario=self.tesorero)
        response = self.client.get(reverse("resumen_contable"), {"anio": 2026, "mes": 11})
        self.assertEqual(response.context["recaudado_anio"], 0)
        self.assertEqual(response.context["saldo"], Decimal("-420.75"))

    def test_aisla_colonia_en_listado_resumen_y_edicion(self):
        ajeno = GastoMensual.objects.create(colonia=self.otra, registrado_por=self.tesorero, **self.datos)
        self.gasto(monto="50")
        for nombre in ("gastos_lista", "resumen_contable"):
            response = self.client.get(reverse(nombre), {"colonia": self.otra.pk, "anio": 2026, "mes": 11})
            self.assertEqual(response.context["colonia"], self.colonia)
            self.assertEqual(response.context["total_gastos" if nombre == "gastos_lista" else "gastos"], 50)
        url = reverse("gasto_editar", args=[ajeno.pk])
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.post(url, self.datos).status_code, 404)

    def test_roles_csrf_y_sin_asignacion(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.tesorero)
        self.assertEqual(client.post(reverse("gasto_crear"), self.datos).status_code, 403)
        for rol in ("RESIDENTE", "GUARDIA"):
            user = User.objects.create_user(rol, rol=rol)
            self.client.force_login(user)
            for nombre in ("gastos_lista", "gasto_crear", "resumen_contable"):
                self.assertEqual(self.client.get(reverse(nombre)).status_code, 403)
            self.assertEqual(self.client.post(reverse("gasto_crear"), self.datos).status_code, 403)
        self.client.force_login(self.tesorero)
        UsuarioColonia.objects.filter(usuario=self.tesorero).delete()
        self.assertEqual(self.client.post(reverse("gasto_crear"), self.datos).status_code, 403)
        response = self.client.get(reverse("resumen_contable"))
        self.assertIsNone(response.context["colonia"])
        self.assertEqual(response.context["gastos_anio"], 0)

    def test_resumen_vacio_y_filtros_invalidos(self):
        response = self.client.get(reverse("resumen_contable"), {"anio": "no", "mes": "99"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["recaudado"], 0)
        self.assertEqual(response.context["gastos"], 0)
        self.assertEqual(response.context["saldo"], 0)

    def test_administrador_solo_elige_colonias_permitidas(self):
        admin = User.objects.create_user("admin", rol="ADMINISTRADOR")
        UsuarioColonia.objects.create(usuario=admin, colonia=self.colonia)
        self.client.force_login(admin)
        response = self.client.post(reverse("gasto_crear"), {**self.datos, "colonia": self.otra.pk})
        self.assertIn("colonia", response.context["form"].errors)
        response = self.client.post(reverse("gasto_crear"), {**self.datos, "colonia": self.colonia.pk})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(GastoMensual.objects.get().registrado_por, admin)
