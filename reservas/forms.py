from django import forms

from core.forms import aplicar_bootstrap

from .models import AreaComun, Reserva


class AreaComunForm(forms.ModelForm):
    class Meta:
        model = AreaComun
        fields = (
            "colonia",
            "nombre",
            "descripcion",
            "reglas",
            "capacidad",
            "costo",
            "imagen",
            "requiere_aprobacion",
            "activa",
        )
        widgets = {
            "descripcion": forms.Textarea(attrs={"rows": 3}),
            "reglas": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, colonias_queryset=None, **kwargs):
        super().__init__(*args, **kwargs)
        if colonias_queryset is not None:
            self.fields["colonia"].queryset = colonias_queryset
        aplicar_bootstrap(self)


class ReservaForm(forms.ModelForm):
    class Meta:
        model = Reserva
        fields = ("area", "fecha", "hora_inicio", "hora_fin", "personas", "motivo")
        widgets = {
            "fecha": forms.DateInput(attrs={"type": "date"}),
            "hora_inicio": forms.TimeInput(attrs={"type": "time"}),
            "hora_fin": forms.TimeInput(attrs={"type": "time"}),
        }

    def __init__(self, *args, areas_queryset=None, **kwargs):
        super().__init__(*args, **kwargs)
        if areas_queryset is not None:
            self.fields["area"].queryset = areas_queryset
        aplicar_bootstrap(self)


class RevisarReservaForm(forms.Form):
    estado = forms.ChoiceField(choices=((Reserva.Estado.APROBADA, "Aprobar"), (Reserva.Estado.RECHAZADA, "Rechazar")))
    observacion = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        aplicar_bootstrap(self)

