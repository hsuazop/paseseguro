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
    colonias = forms.ModelMultipleChoiceField(
        queryset=None,
        required=False,
        label="Colonias asignadas",
        widget=forms.SelectMultiple(attrs={"size": 6}),
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "first_name", "last_name", "identidad", "rol", "is_active")
        labels = {"first_name": "Nombre", "last_name": "Apellido", "is_active": "Activo"}

    def __init__(self, *args, colonias_queryset=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["colonias"].queryset = colonias_queryset
        aplicar_bootstrap(self)

    def save(self, commit=True):
        user = super().save(commit=commit)
        if commit:
            for colonia in self.cleaned_data.get("colonias", []):
                UsuarioColonia.objects.update_or_create(usuario=user, colonia=colonia, defaults={"activa": True})
        return user


def generar_password_temporal(longitud=10):
    alfabeto = string.ascii_letters + string.digits
    while True:
        password = "".join(secrets.choice(alfabeto) for _ in range(longitud))
        if any(c.islower() for c in password) and any(c.isupper() for c in password) and any(c.isdigit() for c in password):
            return password
