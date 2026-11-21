# Vehículos de la residencial

El tesorero accede desde el menú **Vehículos de la residencial**. Puede buscar,
crear, editar y desactivar registros únicamente de su residencial asignada.
Administración puede gestionar las residenciales permitidas. Las comprobaciones
se realizan en el servidor tanto al listar como al guardar o abrir un registro.

`accesos_vehiculocolonia` es independiente de los vehículos del portal residente
y del control de entradas y salidas. Su única clave foránea es `colonia`.
Propietario, teléfono y dirección son texto, sin enlaces a casas ni usuarios.
La desactivación se realiza editando la casilla Activo; no borra el registro.

El menú también incluye **Vehículos de residentes**, que lista los vehículos
vinculados a una casa y a su responsable. Ambos listados tienen el botón
**Registrar vehículo**, que abre `/vehiculos/registrar/` y permite elegir el tipo.
Para vehículos de residentes, las casas disponibles pertenecen únicamente a las
colonias permitidas y deben estar activas y tener un responsable activo.
La colonia y el responsable se obtienen de la casa seleccionada en el servidor.
El registro aparece en **Mis vehículos** del residente; no se copia al padrón.

## Importación

```sh
python manage.py importar_vehiculos_colonia /ruta/archivo.xlsx --colonia-id ID --dry-run
python manage.py importar_vehiculos_colonia /ruta/archivo.xlsx --colonia-id ID
```

Se admiten los dos diseños del Excel Sector 1: placa separada en B/C y placa o
descripción en C. Se omiten filas sin información aparte del consecutivo.
No se asignan casas ni se inventan números de placas. Las columnas SI/NO se
conservan literalmente, porque el archivo no explica su significado.
Los valores originales, archivo, hoja y fila quedan disponibles al editar.

Se conservan filas repetidas de una misma placa y se marcan para revisión: pueden
contener propietarios o teléfonos diferentes. No representan necesariamente
vehículos únicos. Las placas incompletas, nombres ausentes y caracteres ilegibles
también quedan marcados. No se corrigen nombres por suposición.

Repetir exactamente el mismo archivo en la misma colonia no duplica registros ni
sobrescribe correcciones posteriores. Un archivo modificado tiene otra huella:
debe revisarse antes de importarlo, porque constituye un nuevo lote.
El Excel y sus datos personales no se incluyen en Git.
