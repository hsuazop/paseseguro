# Simulación funcional del sistema

Fecha: 18 de noviembre de 2026. Ejecución con datos sintéticos en una base de
pruebas independiente. No se crean pagos de prueba ni se envían alertas reales
a los residentes o guardias de producción.

Resultado: 147 pruebas aprobadas, incluida la doble aprobación simultánea
en PostgreSQL, sin pruebas omitidas.

## Casos cubiertos

| Flujo | Comprobaciones |
| --- | --- |
| Residente envía comprobante | Se almacena archivo y período; la deuda permanece hasta la revisión. |
| Tesorería aprueba | Se registra una sola aplicación, baja el saldo, cambia el estado mensual y el residente puede abrir el recibo PDF. |
| Corrección del período | El pago se aplica al año/mes corregido y conserva el período solicitado originalmente. |
| Abonos | Un abono de 200 sobre 500 deja 300 pendientes; otro de 300 completa el período. |
| Rechazo y reenvío | Rechazar no cobra; un nuevo comprobante puede aprobarse. |
| Duplicados | Dos comprobantes del mismo saldo no producen sobrepago; una segunda aprobación del mismo comprobante no crea otro pago. |
| Aprobaciones simultáneas | Dos operaciones sobre el mismo comprobante: una registra y la otra se bloquea mediante validación y bloqueo de fila. |
| Anulación | Restaura la deuda; la pantalla y el correo manual indican Pago anulado. |
| Correo | Sin dirección se omite; envío manual no aprueba; fallo SMTP no revierte el pago. Pruebas con buzón en memoria. |
| Tesorería mensual | Una solicitud rechazada no oculta otra pendiente del mismo residente. |
| Tarifas y efectivo | Generación mensual, tarifas especiales, historial, altas de vecinos, abonos y reportes. |
| Permisos | Aislamiento de residenciales, roles, CSRF y prohibición de consultar o modificar datos ajenos. |
| Vehículos | Registro independiente por residencial, importación repetible, edición y desactivación. |
| Visitas | Guardia registra entrada, se agota el uso y se rechazan entradas canceladas o agotadas; QR y aislamiento. |
| Reservas | Solicitud, aprobación, cancelación, horarios superpuestos y errores de formulario. No se reactiva una reserva cancelada. |
| Comunidad | Solicitud del residente, respuesta de tesorería y privacidad. |
| SOS | Encolado por residencial, sesión vigente, atención y cierre, reintentos y permisos; transporte push simulado. |
| Administración y documentos | Vistas administrativas, portal, exportaciones y recibos. |

## Fallos reproducidos y corregidos

1. El estado y correo de un comprobante podían seguir indicando aprobación tras
   anular su pago. Se conserva el historial, mostrando el estado financiero real.
2. El comprobante más reciente, si estaba rechazado, ocultaba otro pendiente en
   el control mensual. Ahora se prioriza cualquier solicitud pendiente.
3. El estado de cuenta fallaba con un año no numérico. Usa el año actual ante
   un filtro inválido o fuera de rango.
4. Una reserva sin horas provocaba un error de servidor. Muestra los errores de
   los campos requeridos.
5. Tesorería podía reactivar una reserva cancelada. Ahora se impide y se valida
   nuevamente la disponibilidad al aprobar.

## Comprobación de producción

Auditoría de solo lectura en PostgreSQL de Opalstack: 61 cuotas y 3 pagos.
Cero saldos inconsistentes, cero pagos cuya suma aplicada no coincide y cero
comprobantes aprobados sin un pago asociado, en el momento de la consulta.

## Repetir y límites

Ejecutar `python manage.py test --noinput --verbosity 2`. Los recorridos nuevos
están en `core/test_simulacion.py`. La prueba simultánea requiere una base que
admita `SELECT FOR UPDATE`; no debe interpretarse como verificada si se omite.

La suite cubre los casos descritos; no demuestra ausencia de cualquier fallo
posible. La entrega real de correo sigue pendiente de configurar SMTP. La
recepción push y vibración en Android físico requieren una prueba en dispositivo.
