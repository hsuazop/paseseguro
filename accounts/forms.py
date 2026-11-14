import secrets
import string

from django import forms
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm, UserCreationForm

from core.forms import aplicar_bootstrap

from .models import User, UsuarioColonia


class LoginForm(AuthenticationForm):
    username = forms.CharField(label="Usuario o identidad")
    password = forms.CharField(label="Contraseña", strip=False, widget=forms.PasswordInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        aplicar_bootstrap(self)


class CambioPasswordForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["old_password"].label = "Contraseña actual"
        self.fields["new_password1"].label = "Nueva contraseña"
        self.fields["new_password2"].label = "Confirmar nueva contraseña"
        aplicar_bootstrap(self)


class UsuarioForm(UserCreationForm):
    colonia = forms.ModelChoiceField(
        queryset=None,
        required=True,
        label="Residencial asignada",
        empty_label="Seleccione una residencial",
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "first_name", "last_name", "identidad", "rol", "is_active")
        labels = {
            "username": "Usuario de inicio de sesión",
            "first_name": "Nombre",
            "last_name": "Apellido",
            "identidad": "Identidad",
            "rol": "Tipo de usuario",
            "is_active": "Activo",
        }

    def __init__(self, *args, colonias_queryset=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["colonia"].queryset = colonias_queryset
        self.fields["identidad"].required = False
        aplicar_bootstrap(self)

    def save(self, commit=True):
        user = super().save(commit=commit)
        if commit:
            UsuarioColonia.objects.update_or_create(
                usuario=user,
                colonia=self.cleaned_data["colonia"],
                defaults={"activa": True},
            )
        return user

    def clean(self):
        cleaned_data = super().clean()
        rol = cleaned_data.get("rol")
        colonia = cleaned_data.get("colonia")
        if rol in (User.Rol.GUARDIA, User.Rol.TESORERO) and not colonia:
            self.add_error("colonia", "El guardia y el tesorero deben estar asignados a una residencial.")
        return cleaned_data


def generar_password_temporal(longitud=10):
    alfabeto = string.ascii_letters + string.digits
    while True:
        password = "".join(secrets.choice(alfabeto) for _ in range(longitud))
        if any(c.islower() for c in password) and any(c.isupper() for c in password) and any(c.isdigit() for c in password):
            return password
