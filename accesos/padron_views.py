from django.contrib import messages
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from accounts.permissions import ROLES_FINANCIEROS, roles_requeridos, colonias_permitidas, fijar_colonia_formulario
from core.models import registrar_auditoria
from core.pagination import paginar
from .models import VehiculoColonia
from .forms import VehiculoColoniaForm


@roles_requeridos(*ROLES_FINANCIEROS)
@never_cache
def lista(request):
    registros = VehiculoColonia.objects.filter(colonia__in=colonias_permitidas(request.user)).select_related('colonia')
    q = request.GET.get('q', '').strip()
    if q:
        registros = registros.filter(Q(placa__icontains=''.join(q.split())) | Q(propietario__icontains=q) | Q(telefono__icontains=q) | Q(marca_modelo__icontains=q) | Q(direccion__icontains=q))
    estado = request.GET.get('estado', '')
    if estado == 'revisar': registros = registros.filter(revisar=True)
    elif estado == 'activos': registros = registros.filter(activo=True)
    elif estado == 'inactivos': registros = registros.filter(activo=False)
    return render(request, 'accesos/padron_lista.html', {'pagina': paginar(request, registros), 'q': q, 'estado': estado})


@roles_requeridos(*ROLES_FINANCIEROS)
@never_cache
def formulario(request, pk=None):
    registro = get_object_or_404(VehiculoColonia, pk=pk, colonia__in=colonias_permitidas(request.user)) if pk else VehiculoColonia()
    form = VehiculoColoniaForm(request.POST if request.method == 'POST' else None, instance=registro)
    form.fields['colonia'].queryset = colonias_permitidas(request.user)
    fijar_colonia_formulario(form, request.user)
    if pk:
        # An existing record cannot be moved between communities through the form.
        form.fields.pop('colonia', None)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            registro = form.save()
            registrar_auditoria(usuario=request.user, accion='EDITAR' if pk else 'CREAR', objeto=registro, descripcion='Registro del padrón vehicular de la residencial')
        messages.success(request, 'Registro vehicular guardado.')
        return redirect('padron_vehicular')
    return render(request, 'accesos/padron_form.html', {'form': form, 'registro': registro})
