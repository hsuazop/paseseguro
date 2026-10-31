from django.db import migrations


def migrar_cuentas_a_personas(apps, schema_editor):
    CuotaMensual = apps.get_model("facturacion", "CuotaMensual")
    Pago = apps.get_model("facturacion", "Pago")
    ComprobantePago = apps.get_model("facturacion", "ComprobantePago")

    for cuota in CuotaMensual.objects.select_related("casa").all().iterator():
        cuota.colonia_id = cuota.casa.colonia_id
        cuota.responsable_id = cuota.casa.responsable_actual_id
        cuota.save(update_fields=("colonia", "responsable"))

    for pago in Pago.objects.select_related("casa").all().iterator():
        pago.colonia_id = pago.casa.colonia_id
        pago.save(update_fields=("colonia",))

    for comprobante in ComprobantePago.objects.select_related("casa").all().iterator():
        comprobante.colonia_id = comprobante.casa.colonia_id
        comprobante.save(update_fields=("colonia",))


class Migration(migrations.Migration):
    dependencies = [("facturacion", "0003_remove_cuotamensual_cuota_unica_casa_periodo_and_more")]

    operations = [migrations.RunPython(migrar_cuentas_a_personas, migrations.RunPython.noop)]

