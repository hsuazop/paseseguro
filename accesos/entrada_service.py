import logging

from django.db import transaction
from django.utils import timezone
from .models import FotoEntrada, RegistroVehicular, Vehiculo


def guardar_entrada(form, colonia, usuario):
    archivos_guardados = []
    try:
        with transaction.atomic():
            registro = form.save(commit=False)
            registro.colonia = colonia
            registro.guardia_entrada = usuario
            registro.fecha_entrada = timezone.now()
            vehiculo = Vehiculo.objects.filter(colonia=colonia, placa=registro.placa, activo=True).select_related("casa", "responsable").first() if registro.placa else None
            if vehiculo:
                registro.vehiculo = vehiculo
                registro.casa_destino = vehiculo.casa
                registro.responsable_destino = vehiculo.responsable
                registro.tipo_acceso = RegistroVehicular.TipoAcceso.RESIDENTE
            elif registro.casa_destino_id:
                registro.responsable_destino = registro.casa_destino.responsable_actual
            registro.full_clean()
            registro.save()
            for archivo in form.cleaned_data["fotos"]:
                foto = FotoEntrada(registro=registro)
                foto.archivo.save(archivo.name, archivo, save=False)
                archivos_guardados.append((foto.archivo.storage, foto.archivo.name))
                foto.save()
            return registro
    except Exception:
        # Database rollbacks do not remove files already saved to storage.
        for storage, name in archivos_guardados:
            try:
                storage.delete(name)
            except OSError:
                logging.getLogger(__name__).exception("No se pudo limpiar una foto de una entrada fallida.")
        raise
