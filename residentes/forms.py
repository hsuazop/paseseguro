from django import forms
from django.contrib.auth import password_validation

from core.forms import aplicar_bootstrap

from .models import Responsable


class ResponsableForm(forms.ModelForm):
    crear_usuario = forms.BooleanField(required=False, initial=True, label="Crear usuario residente")

    class Meta:
        model = Responsable
        fields = ("nombre_completo", "identidad", "telefono", "activo")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        aplicar_bootstrap(self)


class AsignarResponsableForm(forms.Form):
    responsable = forms.ModelChoiceField(queryset=Responsable.objects.filter(activo=True), label="Responsable")
    fecha_inicio = forms.DateField(label="Fecha de inicio", widget=forms.DateInput(attrs={"type": "date"}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        aplicar_bootstrap(self)


class PerfilResidenteForm(forms.Form):
    nombre = forms.CharField(max_length=150)
    apellido = forms.CharField(max_length=150, required=False)
    correo = forms.EmailField(required=False)
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
                correo=usuario.email,
                telefono=getattr(responsable, "telefono", ""),
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
