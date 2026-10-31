from django import forms

from core.forms import aplicar_bootstrap

from .models import RegistroVehicular, Vehiculo


class VehiculoForm(forms.ModelForm):
    class Meta:
        model = Vehiculo
        fields = ("placa", "tipo", "marca", "modelo", "color", "descripcion")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["placa"].widget.attrs.update({"autocapitalize": "characters", "placeholder": "HAA1234"})
        aplicar_bootstrap(self)


class RegistroEntradaForm(forms.ModelForm):
    class Meta:
        model = RegistroVehicular
        fields = (
            "placa",
            "tipo_acceso",
            "casa_destino",
            "conductor",
            "identidad_conductor",
            "personas",
            "observaciones",
        )
        widgets = {"observaciones": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, casas_queryset=None, **kwargs):
        super().__init__(*args, **kwargs)
        if casas_queryset is not None:
            self.fields["casa_destino"].queryset = casas_queryset
        self.fields["casa_destino"].required = False
        self.fields["placa"].widget.attrs.update(
            {"autocapitalize": "characters", "autocomplete": "off", "placeholder": "Ingrese la placa"}
        )
        aplicar_bootstrap(self)

