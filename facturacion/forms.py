from django import forms
from decimal import Decimal
from uuid import uuid4
from django.db.models import Q
from django.utils import timezone

from colonias.models import Casa, Colonia
from core.forms import aplicar_bootstrap
from residentes.forms import ETIQUETAS_CUENTA_PAGO
from .adjuntos import validar_adjunto

from .models import ComprobantePago, CuentaPagoColonia, CuotaMensual, Pago, TarifaColonia, TarifaEspecialCasa


class CasaPagoChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, casa):
        residente = casa.responsable_actual
        etiqueta = f"{residente.nombre_completo} — Casa {casa.codigo}"
        return f"{etiqueta} — {residente.identidad}" if residente.identidad else etiqueta


class PagoEfectivoForm(forms.Form):
    casa = CasaPagoChoiceField(label="Residente", queryset=Casa.objects.none())
    mes = forms.TypedChoiceField(choices=CuotaMensual.MESES, coerce=int)
    anio = forms.IntegerField(label="Año", min_value=2020, max_value=2100)
    fecha_pago = forms.DateField(label="Fecha de pago", widget=forms.DateInput(attrs={"type": "date"}))
    monto_total = forms.DecimalField(label="Efectivo recibido", min_value=0.01, max_digits=12, decimal_places=2,
                                    help_text="Puede registrar el pago completo o un abono al período indicado.")
    observaciones = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 2}))

    def __init__(self, *args, colonia, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["casa"].queryset = Casa.objects.filter(
            colonia=colonia, activa=True, responsable_actual__activo=True,
        ).select_related("responsable_actual", "responsable_actual__usuario").order_by("responsable_actual__nombre_completo", "codigo")
        aplicar_bootstrap(self)


class ComprobanteTesoreriaForm(PagoEfectivoForm):
    referencia = forms.CharField(label="Referencia bancaria (opcional)", required=False, max_length=120)
    operacion = forms.UUIDField(initial=uuid4, widget=forms.HiddenInput)
    metodo_pago = forms.ChoiceField(label="Método de pago", choices=[
        (Pago.Metodo.DEPOSITO, "Depósito"), (Pago.Metodo.TRANSFERENCIA, "Transferencia"),
    ])
    banco = ComprobantePago._meta.get_field("banco").formfield(label=ETIQUETAS_CUENTA_PAGO["banco"])
    numero_cuenta = ComprobantePago._meta.get_field("numero_cuenta").formfield(label=ETIQUETAS_CUENTA_PAGO["numero_cuenta"])
    archivo = forms.FileField(label="Comprobante recibido", help_text="Foto JPG, PNG, WEBP o PDF de hasta 8 MB.",
                              widget=forms.FileInput(attrs={"accept": ".jpg,.jpeg,.png,.webp,.pdf"}))
    field_order = ("casa", "mes", "anio", "fecha_pago", "monto_total", "metodo_pago", "banco",
                   "numero_cuenta", "referencia", "archivo", "observaciones", "operacion")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["monto_total"].label = "Monto del comprobante"

    def clean_archivo(self):
        return validar_adjunto(self.cleaned_data["archivo"])


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


class CuotaReferenciaForm(forms.Form):
    colonia = forms.ModelChoiceField(label="Residencial", queryset=Colonia.objects.none())
    monto = forms.DecimalField(label="Cuota mensual de referencia", min_value=Decimal("0.01"), max_digits=12, decimal_places=2)
    anio = forms.IntegerField(label="Año de inicio", min_value=2020, max_value=9999)
    mes = forms.TypedChoiceField(label="Mes de inicio", choices=CuotaMensual.MESES, coerce=int)

    def __init__(self, *args, colonias_queryset, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["colonia"].queryset = colonias_queryset
        self.fields["monto"].help_text = "Se cobra automáticamente cada mes. Los vecinos pueden abonar una parte y completar el saldo después."
        self.fields["mes"].help_text = "Se repite sin fecha final. Las cuotas ya registradas conservan su monto y sus pagos."
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


class DatosComprobanteForm(forms.ModelForm):
    anio = forms.IntegerField(label="Año que pagas", min_value=2020, max_value=9999)
    mes = forms.TypedChoiceField(label="Mes que pagas", coerce=int, choices=CuotaMensual.MESES)

    class Meta:
        model = ComprobantePago
        fields = ("monto", "metodo_pago", "archivo", "comentario")
        widgets = {
            "archivo": forms.ClearableFileInput(attrs={"accept": "image/jpeg,image/png,image/webp,application/pdf,.jpg,.jpeg,.png,.webp,.pdf"}),
            "comentario": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, cuotas_queryset=None, casa=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.casa = casa
        hoy = timezone.localdate()
        self.cuotas_queryset = cuotas_queryset if cuotas_queryset is not None else CuotaMensual.objects.none()
        self.initial.setdefault("anio", hoy.year)
        self.initial.setdefault("mes", hoy.month)
        self.initial.setdefault("metodo_pago", Pago.Metodo.TRANSFERENCIA)
        self.fields["metodo_pago"].label = "Método de pago"
        self.fields["comentario"].label = "Comentario (opcional)"
        self.fields["archivo"].help_text = "Selecciona una foto del celular o un PDF. Formatos: JPG, PNG, WEBP o PDF. Máximo: 8 MB."
        self.order_fields(("anio", "mes", "monto", "metodo_pago", "archivo", "comentario"))
        aplicar_bootstrap(self)

    def clean_archivo(self):
        archivo = self.cleaned_data.get("archivo")
        if archivo and archivo.size > 8 * 1024 * 1024:
            raise forms.ValidationError("El comprobante no puede superar 8 MB.")
        return archivo


class ComprobantePagoForm(DatosComprobanteForm):
    class Meta(DatosComprobanteForm.Meta):
        fields = ("monto", "metodo_pago", "banco", "numero_cuenta", "archivo", "comentario")
        labels = ETIQUETAS_CUENTA_PAGO

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.casa and self.casa.responsable_actual:
            responsable = self.casa.responsable_actual
            self.initial.setdefault("banco", responsable.banco)
            self.initial.setdefault("numero_cuenta", responsable.numero_cuenta)
        self.order_fields(("anio", "mes", "monto", "metodo_pago", "banco", "numero_cuenta", "archivo", "comentario"))

    def clean(self):
        data = super().clean()
        if data.get("anio") and data.get("mes"):
            cuota = self.cuotas_queryset.filter(anio=data["anio"], mes=data["mes"]).first()
            saldo = cuota.saldo if cuota else None
            if self.casa:
                cuota = CuotaMensual.objects.filter(
                    responsable=self.casa.responsable_actual, colonia=self.casa.colonia,
                    anio=data["anio"], mes=data["mes"],
                ).first()
                if cuota and (cuota.estado in (CuotaMensual.Estado.PAGADA, CuotaMensual.Estado.ANULADA) or cuota.saldo <= 0):
                    self.add_error("mes", "Este período ya está pagado o su cuota está anulada. Revisa tu estado de cuenta.")
                    return data
                if cuota:
                    saldo = cuota.saldo
                else:
                    from .services.cuotas import obtener_monto_cuota
                    casa_base = Casa.objects.filter(
                        colonia=self.casa.colonia, responsable_actual=self.casa.responsable_actual, activa=True,
                    ).order_by("pk").first()
                    try:
                        saldo = obtener_monto_cuota(casa_base, data["anio"], data["mes"])
                    except forms.ValidationError:
                        self.add_error("mes", "La residencial aún no tiene una cuota de vigilancia configurada para este período. Comunícate con el administrador.")
                        return data
            if saldo is None:
                self.add_error("mes", "No tienes una cuota pendiente para este año y mes. Elige otro período o consulta a tesorería.")
            elif data.get("monto") and data["monto"] > saldo:
                self.add_error("monto", f"El monto supera el saldo pendiente del período: L {saldo:,.2f}.")
            else:
                data["cuota"] = cuota
        return data

class RevisarComprobanteForm(forms.Form):
    referencia = forms.CharField(label="Referencia bancaria (opcional)", required=False, max_length=120)
    anio = forms.IntegerField(label='Año a registrar', min_value=2020, max_value=9999, required=False)
    mes = forms.TypedChoiceField(label='Mes a registrar', coerce=int, required=False, choices=[('', 'Conservar períodos')] + list(CuotaMensual.MESES))
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

    def clean(self):
        data = super().clean()
        if bool(data.get('anio')) != bool(data.get('mes')):
            raise forms.ValidationError('Indica tanto el año como el mes, o deja ambos vacíos para conservar los períodos.')
        return data


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
