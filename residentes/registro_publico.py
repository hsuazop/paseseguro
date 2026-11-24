import secrets

from django import forms
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_POST

from accesos.forms import VehiculoForm
from accesos.models import Vehiculo
from accounts.models import User
from accounts.permissions import ROLES_FINANCIEROS, colonia_actual, roles_requeridos
from colonias.models import Casa, Colonia, VILLA_OLIMPICA
from core.models import registrar_auditoria
from facturacion.adjuntos import validar_adjunto
from facturacion.forms import DatosComprobanteForm
from facturacion.models import ComprobantePago
from .forms import RegistrarResidenteForm
from .models import ComprobanteInscripcion, RegistroPublico, Responsable
from .services import asignar_responsable, crear_usuario_residente, enviar_credenciales_residente


class FormularioPublico(RegistrarResidenteForm):
    correo = forms.EmailField(
        label="Correo electrónico (opcional)", max_length=150, required=False,
        help_text="Es importante que escribas un correo que revises. Allí recibirás tu contraseña temporal. "
                  "Usa ese correo para ingresar al sistema y, cuando Tesorería confirme tu casa, "
                  "podrás consultar tus recibos y crear pases de visita.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["codigo_casa"].help_text = "Indica el bloque, el número de casa o un punto de referencia."

    def clean_correo(self):
        return self.cleaned_data["correo"].lower()

    def clean_codigo_casa(self):
        return " ".join(self.cleaned_data["codigo_casa"].splitlines())

    def clean_identidad(self):
        return self.cleaned_data["identidad"] or None


def clave_temporal():
    palabras = ("luna nube pino costa monte valle faro lago cedro vela seda roca "
                "isla brisa campo arena mango palma cielo coral perla sol trigo nido "
                "coco torre loma menta plaza rueda bosque playa").split()
    return "-".join(secrets.choice(palabras) for _ in range(4)) + f"-{secrets.randbelow(100000):05}"


class ComprobantePublicoForm(DatosComprobanteForm):
    def clean_archivo(self):
        return validar_adjunto(self.cleaned_data["archivo"])


@transaction.atomic
def inscribir(colonia, datos, vehiculo, comprobante=None):
    Colonia.objects.select_for_update().get(pk=colonia.pk, activa=True)
    correo = datos["correo"]
    if correo and (User.objects.filter(username__iexact=correo).exists() or User.objects.filter(email__iexact=correo).exists()):
        raise ValidationError("Ya existe una cuenta con estos datos. Si necesitas ayuda para ingresar, contacta a Tesorería.")
    responsable = Responsable(
        nombre_completo=datos["nombre_completo"], identidad=datos["identidad"],
        telefono=datos["telefono"], correo=correo,
        banco=datos["banco"], numero_cuenta=datos["numero_cuenta"],
    )
    responsable.full_clean()
    responsable.save()
    usuario, clave = crear_usuario_residente(responsable, password=clave_temporal(), username=correo or None)
    registro = RegistroPublico.objects.create(colonia=colonia, responsable=responsable,
                                             descripcion_casa=datos["codigo_casa"], vehiculo=vehiculo)
    if comprobante:
        ComprobanteInscripcion.objects.create(registro=registro, banco=responsable.banco,
                                              numero_cuenta=responsable.numero_cuenta, **comprobante)
    return usuario, clave


@never_cache
@require_http_methods(["GET", "POST"])
def registro_villa_olimpica(request, con_comprobante=False):
    colonia = get_object_or_404(Colonia, nombre=VILLA_OLIMPICA, activa=True)
    datos = request.POST if request.method == "POST" else None
    form = FormularioPublico(datos, colonia=colonia)
    agregar = bool(datos and datos.get("agregar_vehiculo") == "1")
    vehiculo = VehiculoForm(datos if agregar else None, prefix="vehiculo")
    comprobante = ComprobantePublicoForm(datos, request.FILES or None, prefix="pago") if con_comprobante else None
    pagina = request.resolver_match.url_name
    clave_resultado = f"resultado_{pagina}"
    if form.is_valid() and (not agregar or vehiculo.is_valid()) and (comprobante is None or comprobante.is_valid()):
        try:
            usuario, clave = inscribir(colonia, form.cleaned_data, vehiculo.cleaned_data if agregar else {},
                                       comprobante.cleaned_data if con_comprobante else None)
        except (ValidationError, IntegrityError):
            form.add_error(None, "No se pudo completar el registro con estos datos. Si ya tienes una cuenta, contacta a Tesorería.")
        except OSError:
            form.add_error(None, "No se pudo guardar el archivo. Vuelve a adjuntarlo y envía el formulario de nuevo.")
        else:
            if usuario.email:
                enviado = enviar_credenciales_residente(
                    usuario, clave, colonia, request.build_absolute_uri(reverse("login")), casa_pendiente=True,
                )
                resultado = {"enviado": enviado, "fallo_correo": not enviado}
            else:
                resultado = {"usuario": usuario.username, "clave": clave}
            request.session[clave_resultado] = resultado
            return redirect(pagina)
    return render(request, "residentes/registro_publico.html", {
        "form": form, "colonia": colonia, "agregar_vehiculo": agregar, "form_vehiculo": vehiculo,
        "comprobante": comprobante,
        "resultado": request.session.pop(clave_resultado, None) if request.method == "GET" else None,
    })


@roles_requeridos(*ROLES_FINANCIEROS)
def inscripciones(request):
    _, colonia = colonia_actual(request)
    pendientes = RegistroPublico.objects.filter(colonia=colonia, confirmado=False).select_related("responsable", "adjunto").order_by("pk")
    return render(request, "residentes/inscripciones.html", {"pendientes": pendientes, "colonia": colonia})


@roles_requeridos(*ROLES_FINANCIEROS)
@require_POST
def confirmar_inscripcion(request, pk):
    _, colonia = colonia_actual(request)
    try:
        with transaction.atomic():
            item = get_object_or_404(RegistroPublico.objects.select_for_update(), pk=pk, colonia=colonia, confirmado=False)
            codigo = request.POST.get("codigo_casa", "").strip()
            if not codigo or len(codigo) > 255:
                raise ValidationError("Indica una descripción de casa de hasta 255 caracteres.")
            Colonia.objects.select_for_update().get(pk=colonia.pk, activa=True)
            casa, _ = Casa.objects.select_for_update().get_or_create(colonia=colonia, codigo=codigo, defaults={"numero": codigo})
            if not casa.activa or casa.responsable_actual_id:
                raise ValidationError("Esta casa ya tiene responsable o está inactiva.")
            asignar_responsable(casa=casa, responsable=item.responsable, usuario=request.user)
            if item.vehiculo:
                auto = Vehiculo(casa=casa, colonia=colonia, responsable=item.responsable, **item.vehiculo)
                auto.full_clean()
                auto.save()
            adjunto = getattr(item, "adjunto", None)
            if adjunto:
                recibo = ComprobantePago.objects.create(
                    casa=casa, colonia=colonia, responsable=item.responsable, enviado_por=item.responsable.usuario,
                    archivo=adjunto.archivo.name, monto=adjunto.monto, metodo_pago=adjunto.metodo_pago,
                    banco=adjunto.banco, numero_cuenta=adjunto.numero_cuenta,
                    fecha_pago=timezone.localdate(adjunto.created_at), comentario=adjunto.comentario,
                    periodos_solicitados=[{"anio": adjunto.anio, "mes": adjunto.mes}],
                )
                registrar_auditoria(usuario=request.user, accion="ENVIO_COMPROBANTE", objeto=recibo,
                                    descripcion="Comprobante recibido durante el registro público del residente.")
            item.confirmado = True
            item.save(update_fields=["confirmado", "updated_at"])
            registrar_auditoria(usuario=request.user, accion="CONFIRMAR_REGISTRO", objeto=item,
                                descripcion="Tesorería confirmó la casa de un residente inscrito en el formulario público.")
    except ValidationError as exc:
        messages.error(request, " ".join(exc.messages))
    except IntegrityError:
        messages.error(request, "La casa o la placa ya está registrada. Revisa la asignación.")
    else:
        messages.success(request, "Casa confirmada.")
    return redirect("inscripciones_publicas")
