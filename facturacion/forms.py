from django import forms

from colonias.models import Colonia
from core.forms import aplicar_bootstrap

from .models import ComprobantePago, CuentaPagoColonia, Pago, TarifaColonia, TarifaEspecialCasa


class TarifaColoniaForm(forms.ModelForm):
    class Meta:
        model = TarifaColonia
        fields = ("colonia", "monto", "fecha_inicio", "fecha_fin", "activa")
        widgets = {
            "fecha_inicio": forms.DateInput(attrs={"type": "date"}),
            "fecha_fin": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, colonias_queryset=None, **kwargs):
        super().__init__(*args, **kwargs)
        if colonias_queryset is not None:
            self.fields["colonia"].queryset = colonias_queryset
        aplicar_bootstrap(self)


class TarifaEspecialForm(forms.ModelForm):
    class Meta:
        model = TarifaEspecialCasa
        fields = ("casa", "tipo", "monto", "porcentaje", "motivo", "fecha_inicio", "fecha_fin", "activa")
        widgets = {
            "fecha_inicio": forms.DateInput(attrs={"type": "date"}),
            "fecha_fin": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, casas_queryset=None, **kwargs):
        super().__init__(*args, **kwargs)
        if casas_queryset is not None:
            self.fields["casa"].queryset = casas_queryset
        aplicar_bootstrap(self)


class GenerarCuotasForm(forms.Form):
    colonia = forms.ModelChoiceField(queryset=Colonia.objects.none())
    mes = forms.TypedChoiceField(choices=(), coerce=int)
    anio = forms.IntegerField(label="Año", min_value=2020, max_value=2100)

    def __init__(self, *args, colonias_queryset=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["colonia"].queryset = colonias_queryset or Colonia.objects.none()
        from .models import CuotaMensual
        self.fields["mes"].choices = CuotaMensual.MESES
        aplicar_bootstrap(self)


class PagoForm(forms.Form):
    fecha_pago = forms.DateField(label="Fecha de pago", widget=forms.DateInput(attrs={"type": "date"}))
    monto_total = forms.DecimalField(label="Monto recibido", min_value=0.01, max_digits=12, decimal_places=2)
    metodo_pago = forms.ChoiceField(label="Forma de pago", choices=Pago.Metodo.choices)
    referencia = forms.CharField(required=False, max_length=120)
    observaciones = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        aplicar_bootstrap(self)


class AnularPagoForm(forms.Form):
    motivo = forms.CharField(label="Motivo de anulacion", min_length=5, widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        aplicar_bootstrap(self)


class ComprobantePagoForm(forms.ModelForm):
    class Meta:
        model = ComprobantePago
        fields = ("fecha_pago", "monto", "metodo_pago", "referencia", "archivo", "comentario")
        widgets = {
            "fecha_pago": forms.DateInput(attrs={"type": "date"}),
            "comentario": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["archivo"].help_text = "PDF o imagen. Tamaño máximo: 8 MB."
        aplicar_bootstrap(self)

    def clean_archivo(self):
        archivo = self.cleaned_data.get("archivo")
        if archivo and archivo.size > 8 * 1024 * 1024:
            raise forms.ValidationError("El comprobante no puede superar 8 MB.")
        return archivo


class RevisarComprobanteForm(forms.Form):
    estado = forms.ChoiceField(
        choices=((ComprobantePago.Estado.APROBADO, "Aprobar"), (ComprobantePago.Estado.RECHAZADO, "Rechazar"))
    )
    comentario_revision = forms.CharField(
        label="Comentario de revisión",
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        aplicar_bootstrap(self)


class CuentaPagoColoniaForm(forms.ModelForm):
    class Meta:
        model = CuentaPagoColonia
        fields = (
            "colonia",
            "banco",
            "tipo_cuenta",
            "numero_cuenta",
            "titular",
            "identidad_titular",
            "instrucciones",
            "activa",
        )
        widgets = {"instrucciones": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, colonias_queryset=None, **kwargs):
        super().__init__(*args, **kwargs)
        if colonias_queryset is not None:
            self.fields["colonia"].queryset = colonias_queryset
        aplicar_bootstrap(self)
