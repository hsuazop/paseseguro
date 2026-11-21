from django import forms

from core.forms import aplicar_bootstrap
from colonias.models import Casa

from .models import RegistroVehicular, Vehiculo, VehiculoColonia
from .fotos import MAX_FOTOS_ENTRADA, MAX_BYTES_FOTO


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


class FotosEntradaInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class FotosEntradaField(forms.ImageField):
    def clean(self, data, initial=None):
        files = data if isinstance(data, (list, tuple)) else ([data] if data else [])
        if not files and self.required:
            raise forms.ValidationError("Adjunta al menos una foto de la entrada.")
        if len(files) > MAX_FOTOS_ENTRADA:
            raise forms.ValidationError(f"Puedes adjuntar hasta {MAX_FOTOS_ENTRADA} fotos por entrada.")
        result = []
        for file in files:
            if file.size > MAX_BYTES_FOTO:
                raise forms.ValidationError("Cada foto debe pesar como máximo 8 MB.")
            valid = super().clean(file, initial)
            extension = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp"}.get(valid.image.format)
            if not extension:
                raise forms.ValidationError("Usa fotos JPG, PNG o WEBP.")
            valid.name = "foto" + extension
            result.append(valid)
        return result


class RegistroEntradaForm(forms.ModelForm):
    fotos = FotosEntradaField(label="Fotos de la entrada", required=True,
        widget=FotosEntradaInput(attrs={"accept": "image/jpeg,image/png,image/webp"}),
        help_text="Obligatorio: al menos 1 foto. Hasta 8 fotos JPG, PNG o WEBP, de máximo 8 MB cada una.")
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

    def __init__(self, *args, colonia, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.colonia = colonia
        self.fields["casa_destino"].queryset = Casa.objects.filter(
            colonia=colonia, activa=True,
        ).select_related("responsable_actual", "colonia")
        self.fields["casa_destino"].required = False
        self.fields["placa"].widget.attrs.update(
            {"autocapitalize": "characters", "autocomplete": "off", "placeholder": "Ingrese la placa"}
        )
        aplicar_bootstrap(self)

