from django.core.paginator import Paginator


def paginar(request, queryset, por_pagina=25):
    return Paginator(queryset, por_pagina).get_page(request.GET.get("page"))
