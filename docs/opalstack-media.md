# Archivos subidos en Opalstack

Los archivos se conservan en `MEDIA_ROOT`, separados de `STATIC_ROOT`. Los modelos
ya organizan las cargas por tipo, año y mes de carga. Por ejemplo:

```text
media/comprobantes/2026/11/recibo.pdf
media/comunidad/comunicados/2026/11/imagen.jpg
media/reservas/areas/2026/11/imagen.jpg
```

El período pagado se guarda en la cuota asociada al comprobante. La carpeta usa
el año y mes de carga, aunque se esté pagando un período anterior.

## Configuración del servidor

1. Identificar la carpeta actual `MEDIA_ROOT` de la aplicación. Conservarla si ya
   contiene archivos; no reemplazarla ni moverla sin copiar y verificar los datos.
2. En el entorno que carga el proceso de Django, definir las siguientes variables
   (sustituir la ruta por la ubicación real del proyecto):

   ```sh
   export DJANGO_MEDIA_ROOT=/home/USUARIO/apps/paseseguro/media
   export DJANGO_MEDIA_URL=/media/
   ```

3. Con el intérprete del entorno virtual del servidor ejecutar
   `python manage.py verificar_media`. Esto crea la carpeta si no existe y prueba
   lectura y escritura con un archivo temporal que elimina al terminar.
4. En Opalstack, crear o reutilizar una aplicación **Nginx Static Symlink** del
   mismo usuario de shell. Su destino debe ser exactamente `DJANGO_MEDIA_ROOT`.
   Asociarla al sitio existente en la ruta `/media`, conservando las rutas `/`
   y `/static` que ya tenga el sitio.
5. Reiniciar Django con el procedimiento del despliegue existente para cargar
   las variables. No hace falta una migración para este cambio.
6. Enviar un comprobante de prueba y abrirlo desde tesorería. Verificar que la
   URL `/media/comprobantes/AAAA/MM/archivo` responde correctamente por HTTPS.
   Incluir esta carpeta en los respaldos junto con la base de datos.

`collectstatic` solo publica CSS, JavaScript e imágenes del programa. No copia ni
respalda los archivos que suben los usuarios. WhiteNoise tampoco sirve estos
archivos; en producción se requiere la ruta de Opalstack indicada arriba.

Documentación de referencia:
- https://docs.opalstack.com/topic-guides/symlinks/
- https://docs.opalstack.com/user-guide/sites/

La configuración remota solo queda confirmada después de verificar el panel,
la carpeta real y la apertura de un archivo del servidor.

## Despliegue de Pase Seguro con el acceso SSH actual

El sitio actual dispone de una aplicación Nginx en `/static`. Para publicar
media usando ese acceso, se configura lo siguiente:

```text
DJANGO_MEDIA_ROOT=/home/hector/apps/paseseguro/media
DJANGO_MEDIA_URL=/static/uploads/
/home/hector/apps/paseseguro-static/uploads -> /home/hector/apps/paseseguro/media
```

Los archivos quedan fuera del código y del destino de `collectstatic`. El enlace
`uploads` permite que Nginx los sirva mediante la ruta ya configurada. Las cargas
nuevas se publican como `/static/uploads/comprobantes/AAAA/MM/archivo` y sus
equivalentes de comunidad y reservas. Usar `collectstatic --noinput`, conservando
el enlace `uploads`: no usar `--clear` sobre esta aplicación estática compartida.

La alternativa con una aplicación dedicada en `/media` sigue disponible cuando
se configure esa ruta en el panel o la API de Opalstack.
