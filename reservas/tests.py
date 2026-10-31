from datetime import date, time

from django.core.exceptions import ValidationError
from django.test import TestCase

from accounts.models import User
from colonias.models import Casa, Colonia
from reservas.models import AreaComun, Reserva
from residentes.models import Responsable


class ReservaTests(TestCase):
    def setUp(self):
        self.colonia = Colonia.objects.create(nombre="Residencial Reserva")
        self.user = User.objects.create_user(username="reserva", password="Clave2026!", rol=User.Rol.RESIDENTE)
        self.responsable = Responsable.objects.create(nombre_completo="Reserva Demo", identidad="0101000000001", usuario=self.user)
        self.casa = Casa.objects.create(colonia=self.colonia, codigo="A1", numero="A1", responsable_actual=self.responsable)
        self.area = AreaComun.objects.create(colonia=self.colonia, nombre="Salón", capacidad=20)

    def test_impide_doble_reserva_en_horario_superpuesto(self):
        Reserva.objects.create(
            area=self.area,
            casa=self.casa,
            usuario=self.user,
            fecha=date(2026, 12, 10),
            hora_inicio=time(10),
            hora_fin=time(12),
            personas=5,
        )
        duplicada = Reserva(
            area=self.area,
            casa=self.casa,
            usuario=self.user,
            fecha=date(2026, 12, 10),
            hora_inicio=time(11),
            hora_fin=time(13),
            personas=4,
        )
        with self.assertRaises(ValidationError):
            duplicada.full_clean()

