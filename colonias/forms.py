from django import forms

from core.forms import aplicar_bootstrap

from .models import Casa, Colonia


class ColoniaForm(forms.ModelForm):
    class Meta:
        model = Colonia
        fields = ("nombre", "descripcion", "direccion", "telefono", "activa")
        widgets = {"descripcion": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        aplicar_bootstrap(self)


class CasaForm(forms.ModelForm):
    class Meta:
        model = Casa
        fields = ("colonia", "codigo", "numero", "bloque", "calle", "referencia", "activa")

    def __init__(self, *args, colonias_queryset=None, **kwargs):
        super().__init__(*args, **kwargs)
        if colonias_queryset is not None:
            self.fields["colonia"].queryset = colonias_queryset
        aplicar_bootstrap(self)


class ImportarCasasForm(forms.Form):
    archivo = forms.FileField(label="Archivo Excel (.xlsx)", help_text="Use la plantilla con los encabezados indicados.")
    confirmar = forms.BooleanField(required=False, widget=forms.HiddenInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        aplicar_bootstrap(self)

    def clean_archivo(self):
        archivo = self.cleaned_data["archivo"]
        if not archivo.name.lower().endswith(".xlsx"):
            raise forms.ValidationError("El archivo debe tener formato .xlsx.")
        if archivo.size > 5 * 1024 * 1024:
            raise forms.ValidationError("El archivo no puede superar 5 MB.")
        return archivo
