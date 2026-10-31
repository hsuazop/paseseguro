from django import forms
from django.utils import timezone

from core.forms import aplicar_bootstrap

from .models import Visita


class VisitaForm(forms.ModelForm):
    class Meta:
        model = Visita
        fields = (
            "tipo",
            "temporalidad",
            "nombre_visitante",
            "identidad_visitante",
            "fecha_inicio",
            "fecha_fin",
            "max_usos",
            "max_personas",
        )
        widgets = {
            "fecha_inicio": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
            "fecha_fin": forms.DateTimeInput(attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["fecha_inicio"].input_formats = ("%Y-%m-%dT%H:%M",)
        self.fields["fecha_fin"].input_formats = ("%Y-%m-%dT%H:%M",)
        self.fields["fecha_inicio"].initial = timezone.localtime().replace(second=0, microsecond=0)
        self.fields["identidad_visitante"].required = False
        aplicar_bootstrap(self)

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("temporalidad") == Visita.Temporalidad.UNICA:
            cleaned["max_usos"] = 1
        return cleaned

