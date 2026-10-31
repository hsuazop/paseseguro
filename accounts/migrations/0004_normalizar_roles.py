from django.db import migrations


def normalizar_roles(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    User.objects.filter(rol__in=("TESORERO", "SUPERADMIN")).update(rol="ADMINISTRADOR")


class Migration(migrations.Migration):
    dependencies = [("accounts", "0003_alter_user_rol")]

    operations = [migrations.RunPython(normalizar_roles, migrations.RunPython.noop)]

