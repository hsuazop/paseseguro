from django.db import migrations, models


def copiar_correos(apps, schema_editor):
    Responsable = apps.get_model("residentes", "Responsable")
    for responsable in Responsable.objects.using(schema_editor.connection.alias).filter(usuario__isnull=False).select_related("usuario").iterator():
        if responsable.usuario.email:
            responsable.correo = responsable.usuario.email
            responsable.save(using=schema_editor.connection.alias, update_fields=("correo",))


class Migration(migrations.Migration):
    dependencies = [("residentes", "0001_initial")]
    operations = [
        migrations.AddField(
            model_name="responsable", name="correo",
            field=models.EmailField(blank=True, max_length=254, verbose_name="correo electrónico"),
        ),
        migrations.RunPython(copiar_correos, migrations.RunPython.noop),
    ]
