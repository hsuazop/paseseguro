from django import forms
from accounts.permissions import colonias_permitidas, fijar_colonia_formulario
from core.forms import aplicar_bootstrap
from .models import GastoMensual


class GastoMensualForm(forms.ModelForm):
    class Meta:
        model = GastoMensual
        fields = ("colonia", "tipo", "anio", "mes", "monto", "descripcion")
        widgets = {"descripcion": forms.Textarea(attrs={"rows": 3}),
                   "monto": forms.NumberInput(attrs={"min": "0.01", "step": "0.01"})}

    def __init__(self, *args, usuario, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["colonia"].queryset = colonias_permitidas(usuario)
        if self.instance.pk:
            self.fields.pop("colonia")
        else:
            fijar_colonia_formulario(self, usuario)
        aplicar_bootstrap(self)
