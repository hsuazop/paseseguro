import tempfile
from pathlib import Path
from io import StringIO
from openpyxl import Workbook
from django.test import TestCase, Client
from django.core.management import call_command
from accounts.models import User, UsuarioColonia
from colonias.models import Colonia
from .models import VehiculoColonia


class PadronTests(TestCase):
    def setUp(self):
        self.a = Colonia.objects.create(nombre='A')
        self.b = Colonia.objects.create(nombre='B')
        self.t = User.objects.create_user('tesorero_padron', rol='TESORERO')
        UsuarioColonia.objects.create(usuario=self.t, colonia=self.a)
        self.client.force_login(self.t)
        self.ajeno = VehiculoColonia.objects.create(colonia=self.b, placa='HAA1234', propietario='Privado B')

    def test_tesorero_crea_solo_en_su_colonia_sin_casa_o_responsable(self):
        response = self.client.post('/vehiculos-residencial/nuevo/', {'colonia': self.b.pk, 'placa': 'hbb 1234', 'propietario': 'Vecino A', 'activo': 'on'})
        self.assertEqual(response.status_code, 302)
        obj = VehiculoColonia.objects.get(propietario='Vecino A')
        self.assertEqual(obj.colonia, self.a)
        self.assertEqual(obj.placa, 'HBB1234')
        self.assertEqual([f.name for f in obj._meta.fields if f.is_relation], ['colonia'])

    def test_no_puede_listar_abrir_editar_otra_colonia(self):
        self.assertNotContains(self.client.get('/vehiculos-residencial/?colonia='+str(self.b.pk)), 'Privado B')
        url=f'/vehiculos-residencial/{self.ajeno.pk}/editar/'
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.post(url, {'propietario':'Ataque'}).status_code, 404)
        self.ajeno.refresh_from_db(); self.assertEqual(self.ajeno.propietario, 'Privado B')

    def test_edita_desactiva_sin_mover_colonia(self):
        obj=VehiculoColonia.objects.create(colonia=self.a, placa='HCC1234')
        response=self.client.post(f'/vehiculos-residencial/{obj.pk}/editar/', {'colonia':self.b.pk,'placa':'HCC1234','propietario':'Actualizado'})
        self.assertEqual(response.status_code,302)
        obj.refresh_from_db(); self.assertEqual(obj.colonia,self.a); self.assertFalse(obj.activo)
        self.assertContains(self.client.get('/vehiculos-residencial/?q=actualizado&estado=inactivos'), 'HCC1234')

    def test_otros_roles_y_sin_asignacion(self):
        for rol in ('GUARDIA','RESIDENTE'):
            user=User.objects.create_user(rol,rol=rol); self.client.force_login(user)
            self.assertEqual(self.client.get('/vehiculos-residencial/').status_code,403)
            self.assertEqual(self.client.post('/vehiculos-residencial/nuevo/', {'placa':'HDD1234'}).status_code,403)
        UsuarioColonia.objects.filter(usuario=self.t).update(activa=False)
        self.client.force_login(self.t)
        self.assertEqual(self.client.post('/vehiculos-residencial/nuevo/', {'placa':'HDD1234'}).status_code,403)

    def test_importacion_conserva_duplicados_incompletos_y_es_idempotente(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'vehiculos.xlsx'
            w=Workbook(); s=w.active; s.title='Hoja1'
            s.append(['NO','PLACA',None,'MODELO/MARCA','COLOR','SI','NO','NOMBRE PROPIETARIO','CELULAR','DIRECCION'])
            s.append(['No1','HAA',1234,'Toyota','Rojo','X',None,'Persona','12345678','Casa libre'])
            s.append(['No2','HAA',1234,'Toyota',None,None,None,'Otra persona'])
            s.append(['No3','HAG',None,'Honda'])
            s.append(['No4'])
            s=w.create_sheet('Hoja2');s.append(['#','Nombre','Placa / Vehículo','Teléfono','Apartamento / Observaciones'])
            s.append([1,'Persona sin placa','Matrix Azul',99999999])
            s.append([2,'Nombre','Honda Azul',88888888,'HAD3075'])
            w.save(path)
            call_command('importar_vehiculos_colonia',str(path),colonia_id=self.a.pk,dry_run=True,stdout=StringIO())
            self.assertFalse(VehiculoColonia.objects.filter(colonia=self.a).exists())
            call_command('importar_vehiculos_colonia',str(path),colonia_id=self.a.pk,stdout=StringIO())
            self.assertEqual(VehiculoColonia.objects.filter(colonia=self.a).count(),5)
            self.assertEqual(VehiculoColonia.objects.filter(colonia=self.a,placa='HAA1234',revisar=True).count(),2)
            obj=VehiculoColonia.objects.get(colonia=self.a,placa='HAG');obj.propietario='Corregido';obj.save()
            call_command('importar_vehiculos_colonia',str(path),colonia_id=self.a.pk,stdout=StringIO())
            self.assertEqual(VehiculoColonia.objects.filter(colonia=self.a).count(),5)
            obj.refresh_from_db(); self.assertEqual(obj.propietario,'Corregido')
            self.assertEqual(obj.origen['fila'],4)
            self.assertTrue(VehiculoColonia.objects.filter(colonia=self.a,placa='HAD3075').exists())

    def test_csrf_requerido(self):
        c=Client(enforce_csrf_checks=True);c.force_login(self.t)
        self.assertEqual(c.post('/vehiculos-residencial/nuevo/',{'placa':'HDD1234'}).status_code,403)
