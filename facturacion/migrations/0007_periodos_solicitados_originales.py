from django.db import migrations


def guardar_periodos(apps, schema_editor):
    Comprobante = apps.get_model('facturacion', 'ComprobantePago')
    for item in Comprobante.objects.using(schema_editor.connection.alias).prefetch_related('cuotas').iterator(chunk_size=200):
        if not item.periodos_solicitados:
            item.periodos_solicitados = [{'anio':c.anio, 'mes':c.mes} for c in item.cuotas.all()]
            item.save(update_fields=['periodos_solicitados'])


class Migration(migrations.Migration):
    dependencies = [('facturacion', '0006_comprobantepago_correo_enviado_en_and_more')]
    operations = [migrations.RunPython(guardar_periodos, migrations.RunPython.noop)]
