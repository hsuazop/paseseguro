from django import forms
from django.db.models import Q

from colonias.models import Casa
from django.contrib.auth import password_validation

from core.forms import aplicar_bootstrap

from .models import Responsable


ETIQUETAS_CUENTA_PAGO = {
    "banco": "Banco de destino (opcional)",
    "numero_cuenta": "Número de cuenta de destino (opcional)",
}


class ResponsableForm(forms.ModelForm):
    identidad = forms.CharField(label="Identidad", max_length=20)
    correo = forms.EmailField(label="Correo electrónico", max_length=254, help_text="Dirección donde se enviarán los recibos.")
    crear_usuario = forms.BooleanField(required=False, initial=True, label="Crear usuario residente")

    class Meta:
        model = Responsable
        fields = ("nombre_completo", "identidad", "correo", "telefono", "banco", "numero_cuenta", "activo")
        labels = ETIQUETAS_CUENTA_PAGO

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        aplicar_bootstrap(self)


class AsignarResponsableForm(forms.Form):
    responsable = forms.ModelChoiceField(queryset=Responsable.objects.filter(activo=True), label="Responsable")
    fecha_inicio = forms.DateField(label="Fecha de inicio", widget=forms.DateInput(attrs={"type": "date"}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        aplicar_bootstrap(self)


class CamposBancariosForm(forms.Form):
    banco = Responsable._meta.get_field("banco").formfield(label=ETIQUETAS_CUENTA_PAGO["banco"])
    numero_cuenta = Responsable._meta.get_field("numero_cuenta").formfield(label=ETIQUETAS_CUENTA_PAGO["numero_cuenta"])


class PerfilResidenteForm(CamposBancariosForm):
    field_order = ("nombre", "apellido", "correo", "telefono", "banco", "numero_cuenta")
    nombre = forms.CharField(max_length=150)
    apellido = forms.CharField(max_length=150, required=False)
    correo = forms.EmailField(label="Correo electrónico", max_length=254, help_text="Dirección donde se enviarán los recibos.")
    telefono = forms.CharField(max_length=30, required=False)
    password_actual = forms.CharField(
        label="Contraseña actual",
        required=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )
    password_nueva = forms.CharField(
        label="Nueva contraseña",
        required=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )
    confirmar_password = forms.CharField(
        label="Confirmar nueva contraseña",
        required=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
    )

    def __init__(self, *args, usuario=None, responsable=None, **kwargs):
        self.usuario = usuario
        super().__init__(*args, **kwargs)
        if not self.is_bound and usuario:
            self.initial.update(
                nombre=usuario.first_name,
                apellido=usuario.last_name,
                correo=getattr(responsable, "correo", "") or usuario.email,
                telefono=getattr(responsable, "telefono", ""),
                banco=getattr(responsable, "banco", ""),
                numero_cuenta=getattr(responsable, "numero_cuenta", ""),
            )
        aplicar_bootstrap(self)

    def clean(self):
        cleaned = super().clean()
        actual = cleaned.get("password_actual")
        nueva = cleaned.get("password_nueva")
        confirmar = cleaned.get("confirmar_password")
        if any((actual, nueva, confirmar)):
            if not all((actual, nueva, confirmar)):
                raise forms.ValidationError("Complete los tres campos de contraseña.")
            if not self.usuario.check_password(actual):
                self.add_error("password_actual", "La contraseña actual no es correcta.")
            if nueva != confirmar:
                self.add_error("confirmar_password", "Las contraseñas no coinciden.")
            password_validation.validate_password(nueva, self.usuario)
        return cleaned


class RegistrarResidenteForm(CamposBancariosForm):
    field_order = ("nombre_completo", "identidad", "telefono", "correo", "codigo_casa", "banco", "numero_cuenta")
    nombre_completo = forms.CharField(label="Nombre completo", max_length=180)
    identidad = forms.CharField(label="Identidad (opcional)", max_length=20, required=False)
    telefono = forms.CharField(label="Teléfono (opcional)", max_length=30, required=False)
    correo = forms.EmailField(
        label="Correo electrónico (opcional)", max_length=254, required=False,
        help_text="Conviene pedir el correo para enviarle al residente sus recibos digitales. "
                  "Con o sin correo, puede ingresar a la app con su usuario y contraseña.",
    )
    codigo_casa = forms.CharField(
        label="Descripción de la casa",
        max_length=Casa._meta.get_field("codigo").max_length,
        widget=forms.Textarea(attrs={
            "rows": 4,
            "placeholder": "Ejemplo: Bloque B, casa 12, frente a la cancha de Villa Olímpica.",
        }),
        help_text="Para una casa nueva, indique el bloque, la calle o un punto de referencia. "
                  "Si la casa ya está registrada, escriba su código actual.",
    )

    def __init__(self, *args, colonia, **kwargs):
        super().__init__(*args, **kwargs)
        self.colonia = colonia
        aplicar_bootstrap(self)

    def clean_identidad(self):
        from accounts.models import User
        from residentes.models import Responsable

        identidad = self.cleaned_data["identidad"]
        if not identidad:
            return None
        if (Responsable.objects.filter(identidad=identidad).exists() or
                User.objects.filter(Q(identidad=identidad) | Q(username=identidad)).exists()):
            raise forms.ValidationError("Esta identidad ya está registrada.")
        return identidad

    def clean_codigo_casa(self):
        codigo = " ".join(self.cleaned_data["codigo_casa"].splitlines())
        if Casa.objects.filter(colonia=self.colonia, codigo=codigo).filter(
            Q(activa=False) | Q(responsable_actual__isnull=False)
        ).exists():
            raise forms.ValidationError("Esta casa ya tiene responsable o está inactiva.")
        return codigo
