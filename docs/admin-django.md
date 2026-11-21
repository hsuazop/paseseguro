# Administración de Django

Acceso publicado: https://residencialsegura.com/admin/
Acceso local: http://127.0.0.1:8000/admin/

El archivo local `credenciales` contiene el usuario y la contraseña en la sección
«Django admin (superusuario)». Ese archivo no se incluye en Git ni se publica.

El panel agrupa residenciales, usuarios, residentes, facturación, accesos,
visitas, reservas y comunidad. Incluye todos los modelos instalados y sus
relaciones explícitas, además de permisos, tipos de contenido, sesiones y
registros internos de Django. Las relaciones de grupos y usuarios se administran
en sus propios formularios.

Cada listado permite búsqueda; los modelos operativos incluyen filtros por
residencial, estado, categoría o fecha, según corresponda, y paginación de 40
registros. Las relaciones usan autocompletado. El inicio muestra totales y
accesos al panel operativo; el tema admite escritorio, móvil y modo oscuro.

Los pagos, aplicaciones, numeración de recibos, relaciones de comprobantes y
auditorías se consultan sin edición directa. Un comprobante se aprueba desde
«Revisar comprobante» y un pago se anula desde «Anular pago», para aplicar la
operación completa y mantener los saldos. Las cuotas conservan sus importes e
identidad después de creadas. Las sesiones pueden eliminarse para revocar acceso.

Para crear otra cuenta por terminal, el comando
`manage.py crear_superusuario_admin --username NOMBRE` recibe la contraseña
por entrada estándar, la valida y no la imprime. Si ese nombre ya existe con
otros permisos o contraseña, rechaza la operación sin modificar la cuenta.
