from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import User, UsuarioColonia
from colonias.models import Casa, Colonia
from comunidad.models import Comunicado, DirectorioEntrada
from facturacion.models import CuentaPagoColonia, CuotaMensual, Pago, TarifaColonia, TarifaEspecialCasa
from facturacion.services import generar_cuotas_mes, registrar_pago
from reservas.models import AreaComun
from residentes.models import Responsable
from residentes.services import asignar_responsable


class Command(BaseCommand):
    help = "Crea una colonia y datos financieros de demostracion."

    @transaction.atomic
    def handle(self, *args, **options):
        colonia, _ = Colonia.objects.get_or_create(
            nombre="Residencial Las Palmas",
            defaults={"direccion": "Tegucigalpa", "telefono": "9999-0000"},
        )
        admin, creado = User.objects.get_or_create(
            username="administrador",
            defaults={"first_name": "Ana", "last_name": "Administradora", "rol": User.Rol.ADMINISTRADOR},
        )
        if creado:
            admin.set_password("AdminDemo2026!")
            admin.save()
        guardia, creado = User.objects.get_or_create(
            username="guardia",
            defaults={"first_name": "Marco", "last_name": "Guardia", "rol": User.Rol.GUARDIA},
        )
        if creado:
            guardia.set_password("GuardiaDemo2026!")
            guardia.save()
        UsuarioColonia.objects.get_or_create(usuario=admin, colonia=colonia)
        UsuarioColonia.objects.get_or_create(usuario=guardia, colonia=colonia)
        TarifaColonia.objects.get_or_create(
            colonia=colonia, fecha_inicio=date(2026, 1, 1),
            defaults={"monto": Decimal("500.00")},
        )
        CuentaPagoColonia.objects.get_or_create(
            colonia=colonia,
            numero_cuenta="110012345678",
            defaults={
                "banco": "Banco Atlántida",
                "tipo_cuenta": "Cuenta de cheques",
                "titular": "Residencial Las Palmas",
                "identidad_titular": "08019000000000",
                "instrucciones": "Incluya el número de casa en la referencia y suba su comprobante desde el portal.",
            },
        )

        casas = []
        for numero in range(1, 21):
            identidad = f"08011990{numero:05d}"
            responsable, _ = Responsable.objects.get_or_create(
                identidad=identidad,
                defaults={"nombre_completo": f"Residente Demo {numero:02d}", "telefono": f"9900-{numero:04d}", "creado_por": admin},
            )
            if not responsable.usuario_id:
                usuario = User.objects.create_user(
                    username=identidad, identidad=identidad, password="ResidenteDemo2026!",
                    first_name="Residente", last_name=f"Demo {numero:02d}", rol=User.Rol.RESIDENTE,
                )
                responsable.usuario = usuario
                responsable.save(update_fields=("usuario", "updated_at"))
            casa, _ = Casa.objects.get_or_create(
                colonia=colonia, codigo=f"{numero:03d}",
                defaults={"numero": str(numero)},
            )
            asignar_responsable(casa=casa, responsable=responsable, usuario=admin, fecha_inicio=date(2026, 1, 1))
            casas.append(casa)

        TarifaEspecialCasa.objects.get_or_create(
            casa=casas[6], fecha_inicio=date(2026, 1, 1),
            defaults={
                "tipo": TarifaEspecialCasa.Tipo.MONTO_FIJO, "monto": Decimal("300.00"),
                "motivo": "Tercera edad", "usuario_que_autoriza": admin,
            },
        )
        for mes in (9, 10):
            generar_cuotas_mes(colonia=colonia, anio=2026, mes=mes, usuario=admin)

        def pagar_si_falta(casa, cuota_montos, referencia):
            if Pago.objects.filter(referencia=referencia).exists():
                return
            aplicaciones = []
            total = Decimal("0")
            for mes, monto in cuota_montos:
                cuota = CuotaMensual.objects.get(casa=casa, anio=2026, mes=mes)
                aplicaciones.append({"cuota_id": cuota.pk, "monto": monto})
                total += Decimal(str(monto))
            registrar_pago(
                casa=casa, responsable=casa.responsable_actual, fecha_pago=date(2026, 10, 29),
                monto_total=total, metodo_pago=Pago.Metodo.EFECTIVO,
                aplicaciones=aplicaciones, usuario=admin, referencia=referencia,
            )

        pagar_si_falta(casas[0], [(9, "500"), (10, "500")], "DEMO-CASA-001")
        pagar_si_falta(casas[9], [(10, "200")], "DEMO-CASA-010-PARCIAL")
        pagar_si_falta(casas[14], [(9, "500"), (10, "500")], "DEMO-CASA-015")
        AreaComun.objects.get_or_create(
            colonia=colonia,
            nombre="Área social",
            defaults={
                "descripcion": "Espacio techado para reuniones familiares y eventos de residentes.",
                "reglas": "Horario máximo hasta las 10:00 p. m.",
                "capacidad": 40,
                "costo": Decimal("500.00"),
            },
        )
        Comunicado.objects.get_or_create(
            colonia=colonia,
            titulo="Bienvenidos al nuevo portal residencial",
            defaults={
                "contenido": "Ya puede consultar su estado de cuenta, registrar visitas y enviar comprobantes desde su teléfono.",
                "publicado_por": admin,
            },
        )
        DirectorioEntrada.objects.get_or_create(
            colonia=colonia,
            nombre="Caseta de vigilancia",
            defaults={"categoria": "Seguridad", "telefono": "9999-0001", "descripcion": "Atención las 24 horas"},
        )
        self.stdout.write(self.style.SUCCESS("Datos demo creados o actualizados."))
        self.stdout.write("Administrador: administrador / AdminDemo2026!")
        self.stdout.write("Guardia: guardia / GuardiaDemo2026!")
        self.stdout.write("Residente ejemplo: 0801199000001 / ResidenteDemo2026!")
