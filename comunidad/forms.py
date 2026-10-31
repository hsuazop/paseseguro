from django import forms

from core.forms import aplicar_bootstrap

from .models import AlertaSOS, Clasificado, Comunicado, DirectorioEntrada, DocumentoComunidad, SolicitudMensaje


class ArchivoSeguroMixin:
    limite = 8 * 1024 * 1024

    def validar_archivo(self, archivo):
        if archivo and archivo.size > self.limite:
            raise forms.ValidationError("El archivo no puede superar 8 MB.")
        return archivo


class SolicitudMensajeForm(ArchivoSeguroMixin, forms.ModelForm):
    class Meta:
        model = SolicitudMensaje
        fields = ("tipo", "visibilidad", "asunto", "mensaje", "adjunto")
        widgets = {"mensaje": forms.Textarea(attrs={"rows": 5})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        aplicar_bootstrap(self)

    def clean_adjunto(self):
        return self.validar_archivo(self.cleaned_data.get("adjunto"))


class AlertaSOSForm(ArchivoSeguroMixin, forms.ModelForm):
    class Meta:
        model = AlertaSOS
        fields = ("mensaje", "adjunto")
        widgets = {"mensaje": forms.Textarea(attrs={"rows": 4, "placeholder": "Describe brevemente la emergencia"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        aplicar_bootstrap(self)

    def clean_adjunto(self):
        return self.validar_archivo(self.cleaned_data.get("adjunto"))


class ClasificadoForm(forms.ModelForm):
    class Meta:
        model = Clasificado
        fields = ("titulo", "descripcion", "precio", "telefono", "imagen")
        widgets = {"descripcion": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        aplicar_bootstrap(self)

    def clean_imagen(self):
        imagen = self.cleaned_data.get("imagen")
        if imagen and imagen.size > 8 * 1024 * 1024:
            raise forms.ValidationError("La imagen no puede superar 8 MB.")
        return imagen


class ResponderSolicitudForm(forms.Form):
    estado = forms.ChoiceField(choices=SolicitudMensaje.Estado.choices)
    respuesta = forms.CharField(widget=forms.Textarea(attrs={"rows": 4}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        aplicar_bootstrap(self)


class ComunicadoForm(forms.ModelForm):
    class Meta:
        model = Comunicado
        fields = ("colonia", "titulo", "contenido", "imagen", "adjunto", "activo")
        widgets = {"contenido": forms.Textarea(attrs={"rows": 6})}

    def __init__(self, *args, colonias_queryset=None, **kwargs):
        super().__init__(*args, **kwargs)
        if colonias_queryset is not None:
            self.fields["colonia"].queryset = colonias_queryset
        aplicar_bootstrap(self)


class DirectorioEntradaForm(forms.ModelForm):
    class Meta:
        model = DirectorioEntrada
        fields = ("colonia", "nombre", "categoria", "telefono", "descripcion", "activo")

    def __init__(self, *args, colonias_queryset=None, **kwargs):
        super().__init__(*args, **kwargs)
        if colonias_queryset is not None:
            self.fields["colonia"].queryset = colonias_queryset
        aplicar_bootstrap(self)


class DocumentoComunidadForm(forms.ModelForm):
    class Meta:
        model = DocumentoComunidad
        fields = ("colonia", "titulo", "descripcion", "archivo", "activo")

    def __init__(self, *args, colonias_queryset=None, **kwargs):
        super().__init__(*args, **kwargs)
        if colonias_queryset is not None:
            self.fields["colonia"].queryset = colonias_queryset
        aplicar_bootstrap(self)

