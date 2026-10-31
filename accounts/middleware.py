from django.shortcuts import redirect
from django.urls import reverse


class PasswordTemporalMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and request.user.debe_cambiar_password:
            permitidas = {
                reverse("cambiar_password_obligatorio"),
                reverse("logout"),
            }
            if request.path not in permitidas and not request.path.startswith("/static/"):
                return redirect("cambiar_password_obligatorio")
        return self.get_response(request)
