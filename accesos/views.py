from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from accounts.models import User
from accounts.permissions import ROLES_ACCESO, colonias_permitidas, roles_requeridos
from colonias.models import Casa
from core.pagination import paginar
from residentes.access import casa_del_residente

from .forms import RegistroEntradaForm, VehiculoForm
from .models import RegistroVehicular, Vehiculo


def _colonia_operativa(request):
    colonias = colonias_permitidas(request.user).filter(activa=True)
    colonia_id = request.GET.get("colonia") or request.POST.get("colonia") or request.session.get("colonia_actual")
    colonia = colonias.filter(pk=colonia_id).first() if colonia_id else colonias.first()
    if colonia:
        request.session["colonia_actual"] = colonia.pk
    return colonias, colonia


@roles_requeridos(*ROLES_ACCESO)
def dashboard_guardia(request):
    colonias, colonia = _colonia_operativa(request)
    hoy = timezone.localdate()
    registros = RegistroVehicular.objects.none()
    dentro = entradas_hoy = salidas_hoy = 0
    if colonia:
        registros = RegistroVehicular.objects.filter(colonia=colonia).select_related(
            "vehiculo", "casa_destino", "responsable_destino", "guardia_entrada", "guardia_salida"
        )
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
    casas = Casa.objects.filter(colonia=colonia, activa=True).select_related("responsable_actual")
    form = RegistroEntradaForm(request.POST or None, casas_queryset=casas)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            registro = form.save(commit=False)
            registro.colonia = colonia
            registro.guardia_entrada = request.user
            vehiculo = Vehiculo.objects.filter(colonia=colonia, placa=registro.placa, activo=True).select_related(
                "casa", "responsable"
            ).first()
            if vehiculo:
                registro.vehiculo = vehiculo
                registro.casa_destino = vehiculo.casa
                registro.responsable_destino = vehiculo.responsable
                registro.tipo_acceso = RegistroVehicular.TipoAcceso.RESIDENTE
            elif registro.casa_destino_id:
                registro.responsable_destino = registro.casa_destino.responsable_actual
            registro.full_clean()
            registro.save()
        messages.success(request, f"Entrada de {registro.placa} registrada.")
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
    registros = registros.select_related("casa_destino", "responsable_destino", "guardia_entrada", "guardia_salida")
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

