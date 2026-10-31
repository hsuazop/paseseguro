from decimal import Decimal

from django import template

register = template.Library()

MESES = {
    1: "Enero", 2: "Febrero", 3: "Marzo", 4: "Abril",
    5: "Mayo", 6: "Junio", 7: "Julio", 8: "Agosto",
    9: "Septiembre", 10: "Octubre", 11: "Noviembre", 12: "Diciembre",
}


@register.filter
def moneda(valor):
    try:
        return f"L {Decimal(valor):,.2f}"
    except (ValueError, TypeError):
        return "L 0.00"


@register.filter
def estado_badge(estado):
    return {
        "PAGADA": "success",
        "PENDIENTE": "danger",
        "PARCIAL": "warning",
        "ANULADA": "secondary",
    }.get(estado, "secondary")


@register.filter
def get_item(mapping, key):
    return mapping.get(key)


@register.filter
def nombre_mes(valor):
    try:
        return MESES.get(int(valor), valor)
    except (TypeError, ValueError):
        return valor


@register.simple_tag(takes_context=True)
def query_transform(context, **kwargs):
    query = context["request"].GET.copy()
    for key, value in kwargs.items():
        query[key] = value
    return query.urlencode()
