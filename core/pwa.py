import json
from pathlib import Path

from django.http import JsonResponse
from django.templatetags.static import static
from django.urls import reverse
from django.views.decorators.cache import cache_control
from django.views.decorators.http import require_safe


@require_safe
@cache_control(public=True, max_age=300)
def android_assetlinks(request):
    """Public signing certificate association used by Android and the TWA browser."""
    statements = json.loads(Path(__file__).with_name("android-assetlinks.json").read_text(encoding="utf-8"))
    return JsonResponse(statements, safe=False)


@require_safe
@cache_control(public=True, max_age=3600)
def app_manifest(request):
    """Public identity for the installed web app and its future Android package."""
    return JsonResponse({
        "id": reverse("inicio"),
        "name": "Pase Seguro",
        "short_name": "Pase Seguro",
        "description": "Tu residencial, visitas, pagos y comunidad en un solo lugar.",
        "lang": "es-HN",
        "dir": "ltr",
        "start_url": reverse("inicio"),
        "scope": reverse("inicio"),
        "display": "standalone",
        "background_color": "#f4f7fb",
        "theme_color": "#153b63",
        "icons": [
            {"src": static("core/brand/icon-192.png"), "sizes": "192x192", "type": "image/png", "purpose": "any"},
            {"src": static("core/brand/icon-512.png"), "sizes": "512x512", "type": "image/png", "purpose": "any"},
            {"src": static("core/brand/icon-maskable-512.png"), "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
        ],
    }, content_type="application/manifest+json", json_dumps_params={"ensure_ascii": False})
