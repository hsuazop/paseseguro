# Cuotas de vigilancia automáticas

El administrador define el monto y el primer mes en Tarifas → Definir cuota mensual.
La tarifa se repite sin fecha final y permite abonos: una cuota de L 500 con un
pago aprobado de L 200 conserva L 300 pendientes. Un comprobante enviado todavía
no modifica el saldo: tesorería debe aprobarlo.

Las cuotas existentes, pagadas, parciales y anuladas se conservan. Un cambio de
tarifa cierra la vigencia de la anterior y se aplica a las nuevas cuotas desde
el mes elegido. No recalcula cuotas ya creadas ni cambia pagos históricos.

`manage.py sincronizar_cuotas` crea las cuotas faltantes del mes actual para los
responsables activos de las residenciales activas. Es idempotente y usa la fecha
de Honduras. En producción se ejecuta cada hora, minuto 7, con `flock`; no depende
de que haya visitas al sitio. No tiene un año de vencimiento.

Al consultar las pantallas financieras también se comprueba el mes actual, como
respaldo de la tarea programada. Al enviar un comprobante para otro mes o año se
crea la cuota faltante, usando la tarifa vigente de ese período, dentro de la
misma transacción del envío. Si el archivo o el monto son inválidos, no se crea
una cuota anticipada. No se crean cobros infinitos ni meses anteriores en bloque.

La unicidad por persona, residencial, año y mes y el bloqueo de la residencial
evitan cobros duplicados entre la tarea, el portal y la generación manual. Una
persona con varias casas conserva una cuota por residencial, como antes.

Sin una tarifa configurada no se inventa un importe: el formulario explica que
el administrador debe definir la cuota de vigilancia. La herramienta manual
`/cuotas/generar/` queda disponible para mantenimiento, sin ser un requisito
del flujo de pago.
