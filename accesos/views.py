from datetime import timedelta
import logging
import mimetypes

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError
from django.db.models import Count, Q
from django.http import FileResponse, Http404
from django.views.decorators.cache import never_cache
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.models import User
from accounts.permissions import ROLES_ACCESO, colonia_actual, colonias_permitidas, roles_requeridos
from colonias.models import Casa
from core.pagination import paginar
from residentes.access import casa_del_residente

from .forms import RegistroEntradaForm, VehiculoForm
from .models import FotoEntrada, RegistroVehicular, Vehiculo
from .entrada_service import guardar_entrada


def _colonia_operativa(request):
    return colonia_actual(request)


@roles_requeridos(*ROLES_ACCESO)
def dashboard_guardia(request):
    colonias, colonia = _colonia_operativa(request)
    hoy = timezone.localdate()
    registros = RegistroVehicular.objects.none()
    dentro = entradas_hoy = salidas_hoy = 0
    if colonia:
        registros = RegistroVehicular.objects.filter(colonia=colonia).annotate(total_fotos=Count("fotos")).select_related(
            "vehiculo", "casa_destino", "responsable_destino", "guardia_entrada", "guardia_salida"
        ).order_by("-fecha_entrada", "-pk")
        entradas_hoy = registros.filter(fecha_entrada__date=hoy).count()
        salidas_hoy = registros.filter(fecha_salida__date=hoy).count()
        dentro = registros.filter(fecha_salida__isnull=True).count()
        registros = registros[:30]
    return render(
        request,
        "accesos/dashboard_guardia.html",
        {
            "colonias": colonias,
            "colonia": colonia,
            "registros": registros,
            "entradas_hoy": entradas_hoy,
            "salidas_hoy": salidas_hoy,
            "dentro": dentro,
        },
    )


@roles_requeridos(*ROLES_ACCESO)
def registrar_entrada(request):
    colonias, colonia = _colonia_operativa(request)
    if not colonia:
        messages.error(request, "No tienes una colonia activa asignada.")
        return redirect("dashboard_guardia")
    form = RegistroEntradaForm(request.POST if request.method == "POST" else None, request.FILES or None, colonia=colonia)
    if request.method == "POST" and form.is_valid():
        try:
            registro = guardar_entrada(form, colonia, request.user)
        except ValidationError as exc:
            form.add_error(None, " ".join(exc.messages))
        except (OSError, DatabaseError):
            logging.getLogger(__name__).exception("No se pudo guardar la entrada con sus fotos.")
            form.add_error(None, "No se pudo guardar la entrada. Adjunta las fotos nuevamente e intenta otra vez.")
        else:
            messages.success(request, "Entrada registrada correctamente.")
            return redirect("dashboard_guardia")
    return render(
        request,
        "accesos/entrada_form.html",
        {"form": form, "colonias": colonias, "colonia": colonia},
    )


@roles_requeridos(*ROLES_ACCESO)
def registrar_salida(request, pk):
    registro = get_object_or_404(
        RegistroVehicular,
        pk=pk,
        colonia__in=colonias_permitidas(request.user),
        fecha_salida__isnull=True,
    )
    if request.method == "POST":
        registro.fecha_salida = timezone.now()
        registro.guardia_salida = request.user
        registro.save(update_fields=("fecha_salida", "guardia_salida", "updated_at"))
        messages.success(request, f"Salida de {registro.placa} registrada.")
    return redirect("dashboard_guardia")


@roles_requeridos(*ROLES_ACCESO)
def historial_accesos(request):
    colonias, colonia = _colonia_operativa(request)
    registros = RegistroVehicular.objects.filter(colonia=colonia) if colonia else RegistroVehicular.objects.none()
    registros = registros.annotate(total_fotos=Count("fotos")).select_related("casa_destino", "responsable_destino", "guardia_entrada", "guardia_salida").order_by("-fecha_entrada", "-pk")
    buscar = request.GET.get("q", "").strip()
    if buscar:
        registros = registros.filter(
            Q(placa__icontains=buscar)
            | Q(conductor__icontains=buscar)
            | Q(casa_destino__codigo__icontains=buscar)
            | Q(responsable_destino__nombre_completo__icontains=buscar)
        )
    page_obj = paginar(request, registros, por_pagina=30)
    return render(
        request,
        "accesos/historial.html",
        {"registros": page_obj, "page_obj": page_obj, "colonias": colonias, "colonia": colonia, "buscar": buscar},
    )


@roles_requeridos(*ROLES_ACCESO)
@never_cache
def fotos_entrada(request, pk):
    registro = get_object_or_404(RegistroVehicular.objects.select_related("colonia", "guardia_entrada"),
        pk=pk, colonia__in=colonias_permitidas(request.user))
    return render(request, "accesos/fotos_entrada.html", {"registro": registro, "fotos": registro.fotos.all()})


@roles_requeridos(*ROLES_ACCESO)
@never_cache
def foto_entrada_archivo(request, pk):
    foto = get_object_or_404(FotoEntrada, pk=pk, registro__colonia__in=colonias_permitidas(request.user))
    try:
        archivo = foto.archivo.open("rb")
    except FileNotFoundError:
        raise Http404("Foto no disponible")
    response = FileResponse(archivo, content_type=mimetypes.guess_type(foto.archivo.name)[0] or "application/octet-stream")
    response["X-Content-Type-Options"] = "nosniff"
    return response


@login_required
def mis_vehiculos(request, casa_id):
    if request.user.rol != User.Rol.RESIDENTE:
        raise PermissionDenied
    casa = casa_del_residente(request.user, casa_id)
    vehiculos = Vehiculo.objects.filter(responsable=casa.responsable_actual, colonia=casa.colonia, activo=True)
    return render(request, "accesos/mis_vehiculos.html", {"casa": casa, "vehiculos": vehiculos})


@login_required
def vehiculo_crear(request, casa_id):
    if request.user.rol != User.Rol.RESIDENTE:
        raise PermissionDenied
    casa = casa_del_residente(request.user, casa_id)
    form = VehiculoForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        vehiculo = form.save(commit=False)
        vehiculo.responsable = casa.responsable_actual
        vehiculo.colonia = casa.colonia
        vehiculo.casa = casa
        vehiculo.full_clean()
        vehiculo.save()
        messages.success(request, "Vehículo registrado correctamente.")
        return redirect("mis_vehiculos", casa_id=casa.pk)
    return render(request, "accesos/vehiculo_form.html", {"casa": casa, "form": form})

