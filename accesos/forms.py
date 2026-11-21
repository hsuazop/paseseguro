from django import forms

from core.forms import aplicar_bootstrap
from colonias.models import Casa

from .models import RegistroVehicular, Vehiculo, VehiculoColonia


class VehiculoColoniaForm(forms.ModelForm):
    class Meta:
        model = VehiculoColonia
        fields = ('colonia', 'placa', 'propietario', 'telefono', 'marca_modelo', 'color', 'direccion', 'observaciones', 'revisar', 'activo')
        widgets = {'direccion': forms.Textarea(attrs={'rows': 2}), 'observaciones': forms.Textarea(attrs={'rows': 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        aplicar_bootstrap(self)


class VehiculoForm(forms.ModelForm):
    class Meta:
        model = Vehiculo
        fields = ("placa", "tipo", "marca", "modelo", "color", "descripcion")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["placa"].widget.attrs.update({"autocapitalize": "characters", "placeholder": "HAA1234"})
        aplicar_bootstrap(self)


class CasaVehiculoChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, casa):
        return f"{casa.colonia.nombre} · Casa {casa.codigo} · {casa.responsable_actual.nombre_completo}"


class VehiculoResidenteGestionForm(VehiculoForm):
    casa = CasaVehiculoChoiceField(queryset=Casa.objects.none(), label="Casa y residente")

    class Meta(VehiculoForm.Meta):
        fields = ("casa",) + VehiculoForm.Meta.fields

    def __init__(self, *args, colonias, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["casa"].queryset = Casa.objects.filter(
            colonia__in=colonias, activa=True, responsable_actual__activo=True,
        ).select_related("colonia", "responsable_actual").order_by("colonia__nombre", "codigo")
        self.fields["casa"].help_text = "El vehículo quedará vinculado al responsable actual de esta casa."

    def clean(self):
        data = super().clean()
        casa = data.get("casa")
        placa = ''.join(data.get("placa", "").upper().split())
        data["placa"] = placa
        if casa:
            self.instance.colonia = casa.colonia
            self.instance.responsable = casa.responsable_actual
            if placa and Vehiculo.objects.filter(colonia=casa.colonia, placa=placa).exclude(pk=self.instance.pk).exists():
                self.add_error("placa", "Esta placa ya está registrada en los vehículos de residentes de esta colonia.")
        return data


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

