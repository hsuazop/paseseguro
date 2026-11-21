# Android y alertas SOS

## Funcionamiento

1. El guardia inicia sesión con su cuenta individual y asignación de residencial.
2. Pulsa **Activar notificaciones SOS** y concede el permiso. Se registra una
   suscripción Web Push vinculada a esa sesión. En dispositivos compartidos cada
   guardia debe cerrar la sesión anterior e iniciar la suya.
3. El residente utiliza el SOS existente y confirma el envío del mensaje.
   Django guarda la alerta y las entregas pendientes en una misma transacción.
4. Un proceso independiente consulta la cola cada dos segundos. Valida sesión,
   contraseña, usuario activo, rol y residencial antes de enviar. El proveedor
   recibe únicamente el identificador de alerta y un mensaje cifrado Web Push.
5. El service worker del navegador recibe el evento incluso sin la página abierta,
   consulta los datos con la sesión vigente y solicita una notificación con
   vibración. Muestra nombre del residente, residencial y código de casa.
6. Al tocarla, el guardia ve casa, número, bloque, calle, referencia y mensaje.
   **Voy a atender esta emergencia** registra quién la toma y cuándo. Ese guardia
   puede cerrarla. Otro guardia no puede sobrescribir la asignación.

En primer plano la bandeja también se actualiza cada diez segundos y solicita una
vibración ante alertas nuevas. Cerrar sesión desactiva la suscripción de esa sesión.
Las notificaciones ya mostradas se cierran al enviar el formulario de logout
cuando el navegador permite la comunicación con el service worker.

**ACEPTADA** significa que el proveedor push aceptó el envío, no que el teléfono
lo recibió ni que alguien acudió. La confirmación operativa es **ATENDIENDO**, con
usuario y hora. El monitor administrativo muestra intentos y errores sin exponer
endpoints ni claves. Los fallos temporales tienen hasta cinco intentos; las
suscripciones caducadas (404/410) se desactivan. Se cancelan entregas pendientes
si la alerta ya fue tomada, la sesión terminó o pasaron quince minutos.

## Configuración del servidor

Instalar requirements, ejecutar `python manage.py migrate` y `collectstatic`.
Crear una sola vez una clave privada fuera de Git:

```sh
python manage.py generar_claves_push --archivo /ruta/privada/push-private.pem
```

Guardar la clave pública que imprime en `WEBPUSH_PUBLIC_KEY` y configurar:

```sh
WEBPUSH_PRIVATE_KEY=/ruta/privada/push-private.pem
WEBPUSH_PUBLIC_KEY=clave_publica_generada
WEBPUSH_SUBJECT=https://residencialsegura.com
```

No rotar la clave sin planificar reinscripción de dispositivos. Conservar respaldo
privado. No subir claves VAPID, firma Android ni credenciales a Git.
El envío requiere un proceso supervisado, además del servidor Django:

```sh
python manage.py procesar_push --loop
```

Usar supervisor o un lanzador con bloqueo y recuperación automática. Si el proceso
se detiene, las alertas siguen en la bandeja pero no se despachan hasta recuperarlo.
`python manage.py procesar_push` procesa un lote y permite diagnóstico manual.
El servidor necesita salida HTTPS a los proveedores Web Push. No se requiere
configurar una cuenta Firebase: Chrome usa su proveedor para Web Push con VAPID.

## Android y publicación

El proyecto es una Trusted Web Activity de `com.paseseguro.app`, con delegación de
notificaciones activada. `scripts/prepare-android-project.cjs 1.1.0 3` regenera el
proyecto conservando la clave de firma existente. `scripts/build-android.cjs`
genera APK y AAB firmados. El APK sirve para instalar y probar; el AAB para Play
Console. El API objetivo es 36 y el mínimo 24. Comprobar las políticas vigentes
antes de enviar una nueva versión y aumentar siempre versionCode.

Con Play App Signing, Google puede firmar las instalaciones con un certificado
diferente de la clave de carga. Agregar su SHA-256 de **firma de la aplicación**
a `core/android-assetlinks.json`, manteniendo el certificado de pruebas cuando
corresponda, y publicar la asociación HTTPS. No reemplazarlo por el de carga.
Verificar el dominio tanto con la instalación local como con una instalación de
la pista interna de Play; sin esa asociación puede aparecer la barra del navegador.

Antes de publicación: cuenta Play Console verificada, política de privacidad con
titular y contacto reales, declaración Data safety basada en los flujos reales
(cuentas, domicilio, visitas, pagos, adjuntos y push), clasificación de contenido,
acceso de revisión con cuentas de demostración, ficha e imágenes y pruebas de la
pista interna. Si aplica una exigencia de pruebas cerradas o eliminación de cuenta,
completarla según las condiciones de la cuenta y las políticas de Google. No se
ha enviado esta app a Play Console por el solo hecho de compilar un AAB.

## Prueba de aceptación en dos teléfonos

Antes de emitir un SOS, el guardia puede pulsar **Probar aviso y vibración**.
Envía un push real exclusivamente al dispositivo y sesión que lo solicita, sin
crear una emergencia ni avisar a los demás guardias. Requiere activar primero
las notificaciones y permite una prueba cada 30 segundos. El mensaje de éxito
indica aceptación del proveedor: comprobar visualmente la llegada al teléfono.
Si falla la conexión al consultar una alerta recibida, se muestra un aviso
general sin datos personales para abrir la bandeja cuando vuelva la conexión.

- Usar una residencial y cuentas de demostración. Avisar al personal antes de
  emitir un SOS de prueba para no activar una respuesta real por confusión.
- Teléfono A: guardia asignado, sesión iniciada y push habilitado.
- Teléfono B: residente de esa residencial. Enviar un mensaje que diga PRUEBA.
- Con A bloqueado y la app en segundo plano, comprobar aviso, vibración, nombre y
  casa; abrirlo y confirmar ubicación. Tomar y cerrar la alerta.
- Repetir con A en primer plano y en tablet. Confirmar que otro guardia de otra
  residencial no recibe ni abre los datos.
- Cerrar sesión en A y repetir: no debe recibir datos personales. Probar permiso
  denegado, falta de red, ahorro de batería, No molestar y cambio de contraseña.
- Revisar la cola en admin. Hacer una prueba desde la pista interna de Google Play
  para validar la delegación y el certificado de Play App Signing.

## Límites que deben conocer los guardias

Android, el navegador y el usuario deciden si pueden sonar o vibrar las alertas.
Permiso denegado, No molestar, batería, falta de red, sesión expirada, navegador
forzado a detenerse o el proceso de envío detenido pueden impedir o retrasar la
notificación. No hay vibración permanente, alarma crítica garantizada ni envío
automático a policía o ambulancias. Se necesita un canal alternativo operativo.
El nombre y la casa pueden ser visibles en pantalla bloqueada; configurar esa
visibilidad según el procedimiento de la residencial.

Referencias:
- https://developer.mozilla.org/en-US/docs/Web/API/ServiceWorkerRegistration/showNotification
- https://support.google.com/googleplay/android-developer/answer/11926878
- https://github.com/GoogleChrome/android-browser-helper
