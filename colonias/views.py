from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Count, F, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render

from accounts.models import User, UsuarioColonia
from accounts.permissions import ROLES_GESTION, ROLES_FINANCIEROS, colonias_permitidas, roles_requeridos
from core.models import registrar_auditoria
from core.pagination import paginar
from facturacion.models import CuotaMensual
from residentes.forms import AsignarResponsableForm
from residentes.services import asignar_responsable

from .forms import CasaForm, ColoniaForm, ImportarCasasForm
from .models import Casa, Colonia
from .services import analizar_importacion, guardar_importacion


@roles_requeridos(*ROLES_GESTION)
def colonias_lista(request):
    colonias = colonias_permitidas(request.user).annotate(total_casas=Count("casas")).order_by("nombre")
    return render(request, "colonias/colonias_lista.html", {"colonias": colonias})


@roles_requeridos(User.Rol.ADMINISTRADOR)
def colonia_crear(request):
    form = ColoniaForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        colonia = form.save()
        UsuarioColonia.objects.get_or_create(usuario=request.user, colonia=colonia, defaults={"activa": True})
        registrar_auditoria(usuario=request.user, accion="CREACION_COLONIA", objeto=colonia, descripcion="Colonia creada.")
        messages.success(request, "Colonia creada correctamente.")
        return redirect("colonia_detalle", pk=colonia.pk)
    return render(request, "core/formulario.html", {"form": form, "titulo": "Nueva colonia", "volver": "colonias_lista"})


@roles_requeridos(*ROLES_GESTION)
def colonia_detalle(request, pk):
    colonia = get_object_or_404(colonias_permitidas(request.user), pk=pk)
    return render(request, "colonias/colonia_detalle.html", {"colonia": colonia})


@roles_requeridos(*ROLES_GESTION)
def colonia_editar(request, pk):
    colonia = get_object_or_404(colonias_permitidas(request.user), pk=pk)
    form = ColoniaForm(request.POST or None, instance=colonia)
    if request.method == "POST" and form.is_valid():
        form.save()
        registrar_auditoria(usuario=request.user, accion="EDICION_COLONIA", objeto=colonia, descripcion="Colonia actualizada.")
        messages.success(request, "Colonia actualizada.")
        return redirect("colonia_detalle", pk=colonia.pk)
    return render(request, "core/formulario.html", {"form": form, "titulo": "Editar colonia", "volver": "colonia_detalle", "volver_kwargs": {"pk": pk}})


@roles_requeridos(*ROLES_FINANCIEROS)
def casas_lista(request):
    casas = Casa.objects.filter(colonia__in=colonias_permitidas(request.user)).select_related("colonia", "responsable_actual")
    buscar = request.GET.get("q", "").strip()
    colonia_id = request.GET.get("colonia", "")
    if buscar:
        casas = casas.filter(
            Q(codigo__icontains=buscar) | Q(numero__icontains=buscar)
            | Q(responsable_actual__nombre_completo__icontains=buscar)
            | Q(responsable_actual__identidad__icontains=buscar)
            | Q(responsable_actual__telefono__icontains=buscar)
        )
    if colonia_id:
        casas = casas.filter(colonia_id=colonia_id)
    casas = casas.annotate(
        deuda=Sum(
            "responsable_actual__cuotas__saldo",
            filter=Q(responsable_actual__cuotas__colonia_id=F("colonia_id"))
            & ~Q(responsable_actual__cuotas__estado=CuotaMensual.Estado.ANULADA),
        )
    )
    page_obj = paginar(request, casas)
    return render(request, "colonias/casas_lista.html", {
        "casas": page_obj, "page_obj": page_obj, "buscar": buscar, "colonia_id": colonia_id,
        "colonias": colonias_permitidas(request.user),
    })


@roles_requeridos(*ROLES_FINANCIEROS)
def casa_detalle(request, pk):
    casa = get_object_or_404(
        Casa.objects.select_related("colonia", "responsable_actual").filter(colonia__in=colonias_permitidas(request.user)),
        pk=pk,
    )
    cuotas = (
        CuotaMensual.objects.filter(responsable=casa.responsable_actual, colonia=casa.colonia)
        .exclude(estado=CuotaMensual.Estado.ANULADA)
        .order_by("-anio", "-mes")
        if casa.responsable_actual_id
        else CuotaMensual.objects.none()
    )
    return render(request, "colonias/casa_detalle.html", {"casa": casa, "cuotas": cuotas})


@roles_requeridos(*ROLES_GESTION)
def casa_crear(request):
    form = CasaForm(request.POST or None, colonias_queryset=colonias_permitidas(request.user).filter(activa=True))
    if request.method == "POST" and form.is_valid():
        casa = form.save()
        registrar_auditoria(usuario=request.user, accion="CREACION_CASA", objeto=casa, descripcion="Casa creada.")
        messages.success(request, "Casa creada correctamente. Ahora puede asignar su responsable.")
        return redirect("casa_detalle", pk=casa.pk)
    return render(request, "core/formulario.html", {"form": form, "titulo": "Nueva casa", "volver": "casas_lista"})


@roles_requeridos(*ROLES_GESTION)
def casa_editar(request, pk):
    casa = get_object_or_404(Casa.objects.filter(colonia__in=colonias_permitidas(request.user)), pk=pk)
    form = CasaForm(request.POST or None, instance=casa, colonias_queryset=colonias_permitidas(request.user))
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Casa actualizada.")
        return redirect("casa_detalle", pk=casa.pk)
    return render(request, "core/formulario.html", {"form": form, "titulo": "Editar casa", "volver": "casa_detalle", "volver_kwargs": {"pk": pk}})


@roles_requeridos(*ROLES_GESTION)
def casa_asignar_responsable(request, pk):
    casa = get_object_or_404(Casa.objects.filter(colonia__in=colonias_permitidas(request.user)), pk=pk)
    form = AsignarResponsableForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        asignar_responsable(casa=casa, usuario=request.user, **form.cleaned_data)
        messages.success(request, "Responsable asignado correctamente.")
        return redirect("casa_detalle", pk=casa.pk)
    return render(request, "core/formulario.html", {"form": form, "titulo": f"Asignar responsable a Casa {casa.codigo}", "volver": "casa_detalle", "volver_kwargs": {"pk": pk}})


@roles_requeridos(*ROLES_GESTION)
def importar_casas(request):
    datos = request.session.get("importacion_casas_datos")
    errores = []
    passwords = None
    if request.method == "POST" and request.POST.get("confirmar") == "1":
        if not datos:
            messages.error(request, "La vista previa expiro. Cargue el archivo nuevamente.")
            return redirect("importar_casas")
        try:
            creadas, passwords = guardar_importacion(datos, request.user)
            del request.session["importacion_casas_datos"]
            messages.success(request, f"Se importaron {creadas} casas correctamente.")
        except ValidationError as exc:
            errores = exc.messages
        return render(request, "colonias/importar_casas.html", {"form": ImportarCasasForm(), "passwords": passwords, "errores": errores})

    form = ImportarCasasForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        try:
            datos, errores = analizar_importacion(form.cleaned_data["archivo"], colonias_permitidas(request.user))
            request.session["importacion_casas_datos"] = datos
        except (ValidationError, ValueError) as exc:
            errores = getattr(exc, "messages", [str(exc)])
            datos = []
    return render(request, "colonias/importar_casas.html", {"form": form, "datos": datos, "errores": errores})
