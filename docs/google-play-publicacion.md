# Preparación de Google Play

Estado: compilación de lanzamiento preparada, todavía no enviada a Play Console.

## Archivos

- AAB firmado: `outputs/android/ResidenciaSegura-1.2.0.aab`.
- APK firmado para prueba directa: `outputs/android/ResidenciaSegura-1.2.0.apk`.
- Identificador: `com.paseseguro.app`. Versión 1.2.0, código 4.
- Android mínimo API 24, objetivo API 36.
- `outputs/android/play`: icono, gráfico y capturas con datos sintéticos.
- `outputs/android/build-report.json`: hashes y comprobaciones de firma.
- No cargar el keystore, contraseñas ni claves VAPID en la ficha pública.

## Texto de ficha propuesto

**Nombre:** Residencia Segura

**Descripción corta:** Gestiona cuotas, visitas y comunicaciones de tu residencial.

**Descripción completa:**

Residencia Segura organiza las gestiones cotidianas de comunidades residenciales.
La administración habilita las cuentas y asigna el acceso según la función
de cada persona y la residencial correspondiente.

Los residentes pueden consultar su estado de cuenta, enviar comprobantes,
registrar visitas y acceder a comunicados, solicitudes, documentos,
clasificados y reservaciones de áreas comunes disponibles en su residencial.

Tesorería revisa comprobantes y registra pagos. El personal de acceso cuenta con
registro de entradas y salidas vehiculares e historial de movimientos.

El botón SOS permite registrar un aviso con el mensaje del residente y los datos
de su casa. Los guardias habilitados de esa residencial pueden recibir
notificaciones, consultar la alerta y registrar que la están atendiendo.
Las notificaciones requieren permiso, sesión vigente y conexión. Su sonido y
vibración dependen de la configuración del dispositivo. SOS no contacta
automáticamente a servicios públicos de emergencia.

La interfaz se adapta a teléfonos y tablets. Para utilizar el sistema se requiere
una cuenta proporcionada por la administración de una residencial participante.
La conexión a internet es necesaria para consultar y guardar información.

## Información pendiente del titular

Confirmar nombre legal, correo de soporte, país y entidad que actúa como proveedor
y responsable de los datos. Definir con las residenciales conservación de datos,
eliminación y atención de solicitudes. Publicar una política de privacidad real en
una URL HTTPS accesible sin iniciar sesión. Este archivo no sustituye esa política.

## Inventario preliminar para Data safety

Revisar las respuestas en Play Console contra el despliegue definitivo y los SDK
incluidos. No marcar categorías por suposición ni usar este inventario como una
declaración ya aprobada.

| Información utilizada | Finalidad identificada |
| --- | --- |
| Usuario, nombre e identidad registrada | Acceso y asociación con la residencia |
| Casa, bloque, calle y referencia registrados | Gestión residencial y atención del SOS |
| Datos de visitantes y vehículos | Registro de visitas y movimientos |
| Montos, períodos y soportes de pago | Revisión de cuotas y comprobantes |
| Mensajes y archivos enviados | Solicitudes y comunicación comunitaria |
| Endpoint push y claves de suscripción | Entrega de notificaciones por sesión |
| Estado y responsable de atención del SOS | Seguimiento operativo de la alerta |

La casa corresponde a una dirección registrada, no a geolocalización GPS en vivo.
El alojamiento y los proveedores Web Push participan en el procesamiento técnico.
Determinar las declaraciones de recopilación, compartición y eliminación según
los contratos, prácticas efectivas y definiciones de Google Play.

## Secuencia de publicación

1. Verificar la cuenta de desarrollador y crear la app con el titular correcto.
2. Completar política de privacidad, soporte, Data safety, contenido y audiencia.
3. Revisar requisitos de eliminación de cuenta y de pruebas aplicables a esa cuenta.
4. Subir el AAB a una pista interna y configurar Play App Signing.
5. Agregar el certificado SHA-256 de firma de Play a assetlinks.json del dominio.
6. Proporcionar acceso de revisión con perfiles de demostración, sin contraseñas
   en archivos públicos ni acceso a datos de clientes reales.
7. Instalar desde la pista interna en dos teléfonos. Probar SOS, segundo plano,
   pantalla bloqueada, permisos denegados, logout y aislamiento entre residenciales.
8. Corregir cualquier incidencia y solicitar revisión de la versión.

Cada publicación posterior debe usar un versionCode superior al ya utilizado.
Revisar políticas vigentes en https://support.google.com/googleplay/android-developer/
antes de enviar. El AAB firmado no equivale a aprobación de Google Play.
