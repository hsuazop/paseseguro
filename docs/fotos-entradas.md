# Fotos de entradas

El guardia puede tomar fotos sucesivas con la cámara del móvil o elegir varias
imágenes de la galería. Se exige al menos una foto: hasta ocho por entrada, JPG,
PNG o WEBP, con un máximo de 8 MB por archivo. El navegador ofrece la cámara
trasera cuando admite `capture`; en equipos sin cámara puede abrir el selector
de archivos. Se pueden quitar fotos antes de confirmar.

Los dem?s campos de la entrada son opcionales. La fecha y hora se guardan al
confirmar, y la colonia y el guardia se asignan desde la sesi?n autenticada.
Solo se ofrecen casas activas de esa colonia.

El servidor valida cada imagen y guarda un registro `FotoEntrada` por archivo.
Si falla el guardado, revierte la entrada y elimina los archivos que alcanzó a
guardar. Después de un error de formulario hay que volver a adjuntar las fotos.

Las fotos se consultan desde el panel o historial de accesos. La galería y cada
archivo verifican el rol y la colonia del usuario. No se publican bajo MEDIA_URL.

Para desplegar: instalar los requisitos (incluyen Pillow), aplicar la migración
`accesos.0004_alter_registrovehicular_personas_and_more` y ejecutar collectstatic. `DJANGO_PRIVATE_MEDIA_ROOT`
permite definir una carpeta privada persistente; el valor predeterminado es
`BASE_DIR/private_media`. Mantenerla fuera de las rutas públicas de Nginx e
incluirla en los respaldos. El servidor debe permitir solicitudes multipart de
hasta 64 MB de fotos, más los campos del formulario.
