from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache

from accounts.permissions import ROLES_FINANCIEROS, colonias_permitidas, fijar_colonia_formulario, roles_requeridos
from core.models import registrar_auditoria
from core.pagination import paginar
from .forms import VehiculoColoniaForm, VehiculoResidenteGestionForm
from .models import Vehiculo


@roles_requeridos(*ROLES_FINANCIEROS)
@never_cache
def lista_residentes(request):
    vehiculos = Vehiculo.objects.filter(colonia__in=colonias_permitidas(request.user)).select_related(
        "colonia", "casa", "responsable",
    )
    q = request.GET.get("q", "").strip()
    if q:
        vehiculos = vehiculos.filter(
            Q(placa__icontains=''.join(q.split())) | Q(responsable__nombre_completo__icontains=q) |
            Q(casa__codigo__icontains=q) | Q(marca__icontains=q) | Q(modelo__icontains=q)
        )
    estado = request.GET.get("estado", "")
    if estado in ("activos", "inactivos"):
        vehiculos = vehiculos.filter(activo=estado == "activos")
    pagina = paginar(request, vehiculos)
    return render(request, "accesos/vehiculos_residentes_gestion.html", {
        "vehiculos": pagina, "page_obj": pagina, "q": q, "estado": estado,
    })


@roles_requeridos(*ROLES_FINANCIEROS)
@never_cache
def registrar(request):
    colonias = colonias_permitidas(request.user)
    if not colonias.exists():
        raise PermissionDenied("No tiene una residencial asignada.")
    tipo = request.POST.get("tipo_registro") if request.method == "POST" else request.GET.get("tipo", "padron")
    if tipo not in ("padron", "residente"):
        raise PermissionDenied("Tipo de registro no válido.")
    datos = request.POST if request.method == "POST" else None
    if tipo == "padron":
        form = VehiculoColoniaForm(datos)
        form.fields["colonia"].queryset = colonias
        fijar_colonia_formulario(form, request.user)
        volver = "padron_vehicular"
    else:
        form = VehiculoResidenteGestionForm(datos, colonias=colonias)
        volver = "vehiculos_residentes_gestion"
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                registro = form.save(commit=False)
                registro.full_clean()
                registro.save()
                registrar_auditoria(usuario=request.user, accion="CREAR", objeto=registro,
                    descripcion="Registro de vehículo en padrón residencial" if tipo == "padron" else "Registro de vehículo vinculado a residente")
        except ValidationError as exc:
            form.add_error(None, " ".join(exc.messages))
        except IntegrityError:
            form.add_error(None, "No se pudo guardar. Revisa si el vehículo ya está registrado e intenta nuevamente.")
        else:
            messages.success(request, "Vehículo registrado correctamente.")
            return redirect(volver)
    return render(request, "accesos/vehiculo_registrar_gestion.html", {
        "form": form, "tipo_registro": tipo, "volver": volver,
    })
