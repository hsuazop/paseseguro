from datetime import date
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import transaction
from openpyxl import load_workbook

from facturacion.models import TarifaEspecialCasa
from residentes.models import Responsable
from residentes.services import asignar_responsable, crear_usuario_residente

from .models import Casa, Colonia


ENCABEZADOS = (
    "colonia", "codigo_casa", "numero", "bloque", "nombre_responsable",
    "identidad", "telefono", "cuota_especial",
)


def analizar_importacion(archivo, colonias_permitidas):
    workbook = load_workbook(archivo, read_only=True, data_only=True)
    worksheet = workbook.active
    filas = worksheet.iter_rows(values_only=True)
    encabezados = tuple(str(v or "").strip().lower() for v in next(filas, ()))
    if encabezados[:len(ENCABEZADOS)] != ENCABEZADOS:
        raise ValidationError("Los encabezados no coinciden con la plantilla esperada.")

    permitidas = {c.nombre.strip().lower(): c for c in colonias_permitidas}
    datos = []
    errores = []
    casas_archivo = set()
    identidades_archivo = {}
    for numero_fila, valores in enumerate(filas, start=2):
        if not any(v not in (None, "") for v in valores):
            continue
        fila = dict(zip(ENCABEZADOS, valores[:len(ENCABEZADOS)]))
        fila = {k: str(v).strip() if v is not None else "" for k, v in fila.items()}
        fila["fila"] = numero_fila
        colonia = permitidas.get(fila["colonia"].lower())
        errores_fila = []
        if not colonia:
            errores_fila.append("Colonia inexistente o no autorizada.")
        if not fila["codigo_casa"]:
            errores_fila.append("Falta el codigo de casa.")
        if not fila["numero"]:
            errores_fila.append("Falta el numero de casa.")
        if not fila["nombre_responsable"]:
            errores_fila.append("Falta el nombre del responsable.")
        if not fila["identidad"]:
            errores_fila.append("Falta la identidad.")

        clave_casa = (colonia.pk if colonia else None, fila["codigo_casa"].lower())
        if clave_casa in casas_archivo:
            errores_fila.append("Casa repetida dentro del archivo.")
        casas_archivo.add(clave_casa)
        if colonia and Casa.objects.filter(colonia=colonia, codigo__iexact=fila["codigo_casa"]).exists():
            errores_fila.append("La casa ya existe en el sistema.")

        identidad = fila["identidad"]
        nombre_previo = identidades_archivo.get(identidad)
        if nombre_previo and nombre_previo.lower() != fila["nombre_responsable"].lower():
            errores_fila.append("La identidad aparece con nombres diferentes.")
        identidades_archivo[identidad] = fila["nombre_responsable"]
        existente = Responsable.objects.filter(identidad=identidad).first()
        if existente and existente.nombre_completo.strip().lower() != fila["nombre_responsable"].lower():
            errores_fila.append("La identidad ya existe con otro nombre.")

        if fila["cuota_especial"]:
            try:
                cuota = Decimal(fila["cuota_especial"])
                if cuota <= 0:
                    raise InvalidOperation
                fila["cuota_especial"] = str(cuota.quantize(Decimal("0.01")))
            except (InvalidOperation, ValueError):
                errores_fila.append("La cuota especial debe ser un monto positivo.")

        fila["colonia_id"] = colonia.pk if colonia else None
        fila["errores"] = errores_fila
        datos.append(fila)
        errores.extend([f"Fila {numero_fila}: {error}" for error in errores_fila])
    workbook.close()
    if not datos:
        errores.append("El archivo no contiene filas de datos.")
    return datos, errores


@transaction.atomic
def guardar_importacion(datos, usuario):
    creadas = 0
    passwords = []
    for fila in datos:
        if fila.get("errores"):
            raise ValidationError("No se puede guardar una importacion con errores.")
        colonia = Colonia.objects.get(pk=fila["colonia_id"])
        responsable, _ = Responsable.objects.get_or_create(
            identidad=fila["identidad"],
            defaults={
                "nombre_completo": fila["nombre_responsable"],
                "telefono": fila["telefono"],
            },
        )
        _, temporal = crear_usuario_residente(responsable)
        if temporal:
            passwords.append({"identidad": responsable.identidad, "password": temporal})
        casa = Casa.objects.create(
            colonia=colonia,
            codigo=fila["codigo_casa"],
            numero=fila["numero"],
            bloque=fila["bloque"],
            responsable_actual=None,
        )
        asignar_responsable(casa=casa, responsable=responsable, usuario=usuario, fecha_inicio=date.today())
        if fila.get("cuota_especial"):
            TarifaEspecialCasa.objects.create(
                casa=casa,
                tipo=TarifaEspecialCasa.Tipo.MONTO_FIJO,
                monto=Decimal(fila["cuota_especial"]),
                motivo="Importacion inicial",
                fecha_inicio=date.today(),
                usuario_que_autoriza=usuario,
            )
        creadas += 1
    return creadas, passwords
