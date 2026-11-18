# Revisión de comprobantes por tesorería

En **Validar comprobantes** se muestran todas las solicitudes de la residencial,
con filtros de estado y paginación. Las fotos se amplían al pulsar su miniatura;
los PDF se abren desde Ver PDF. El archivo original siempre queda disponible.

El tesorero puede corregir año y mes antes de **Guardar y aceptar comprobante**.
Se aplica el pago al período corregido, se conserva el período original y se
registra la revisión en auditoría. La aprobación bloquea una segunda aplicación
o un cambio de período posterior. Un rechazo no registra pagos. Si el monto
excede el saldo, se revierte toda la operación y se muestra el motivo.

Al guardar la revisión se intenta notificar al residente. Se usa el correo del
usuario que envió el comprobante y, si está vacío, el del responsable asociado.
Si ambos están vacíos, se omite el envío. **Enviar correo** notifica únicamente
el estado actual: no acepta el comprobante ni cambia cuotas, períodos o saldos.
Un fallo SMTP no revierte el pago y permite reintentar con ese botón.
El listado muestra la fecha y el estado del último correo enviado.

## Correo en producción

Configurar en el archivo privado `production.env`:

```sh
EMAIL_HOST=servidor-smtp-del-remitente
EMAIL_PORT=587
EMAIL_HOST_USER=cuenta-del-remitente
EMAIL_HOST_PASSWORD=secreto
EMAIL_USE_TLS=true
EMAIL_USE_SSL=false
DEFAULT_FROM_EMAIL=cuenta-del-remitente
```

Para SSL en puerto 465 usar TLS=false y SSL=true. Reiniciar Django después de
cambiar variables. No guardar secretos en Git. El backend de pruebas usa memoria
y no entrega correo real. Un envío aceptado por SMTP no garantiza llegada a la
bandeja de entrada: revisar rebotes y configuración del dominio del remitente.
