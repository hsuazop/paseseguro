"""Read the two layouts in INFORMACION VEHICULAR SECTOR 1 without guessing data."""
import hashlib
import re
from collections import Counter
from pathlib import Path
from openpyxl import load_workbook
from openpyxl.utils import get_column_letter


def texto(value):
    if value is None: return ''
    if isinstance(value, float) and value.is_integer(): return str(int(value))
    return str(value).strip()


def leer_padron(archivo):
    path = Path(archivo)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    workbook = load_workbook(path, data_only=True, read_only=True)
    registros, omitidas = [], []
    try:
        for sheet in workbook:
            rows = sheet.iter_rows(values_only=True)
            header = [texto(v).upper() for v in next(rows, ())]
            layout = 'separada' if header[:2] == ['NO', 'PLACA'] else 'unida' if header[:2] == ['#', 'NOMBRE'] else None
            for number, raw in enumerate(rows, 2):
                cells = [texto(v) for v in raw]
                if not any(cells[1:10]):
                    omitidas.append({'hoja': sheet.title, 'fila': number})
                    continue
                if layout is None: raise ValueError(f'Formato no reconocido: {sheet.title}')
                cells += [''] * (14-len(cells))
                notes = []
                if layout == 'separada':
                    placa = cells[1]+cells[2]
                    marca, color, nombre, telefono, direccion = cells[3], cells[4], cells[7], cells[8], cells[9]
                    if cells[5] or cells[6]:
                        notes.append(f'Columnas originales sin significado indicado: SI={cells[5] or "vacío"}; NO={cells[6] or "vacío"}.')
                else:
                    nombre, telefono, direccion = cells[1], cells[3], cells[4]
                    valor = ''.join(cells[2].upper().split())
                    placa, marca = (valor, '') if re.fullmatch(r'[A-Z]{2,3}\d{4}', valor) else ('', cells[2])
                    color = ''
                    # Some rows put the plate in the observations column; retain that original text too.
                    if not placa and re.fullmatch(r'[A-Z]{2,3}\d{4}', ''.join(direccion.upper().split())):
                        placa = ''.join(direccion.upper().split())
                        notes.append('Placa encontrada en Apartamento / Observaciones.')
                placa = ''.join(placa.upper().split())
                reasons = []
                if not re.fullmatch(r'[A-Z]{2,3}\d{4}', placa): reasons.append('Placa ausente, incompleta o con formato por confirmar')
                if not nombre: reasons.append('Propietario no indicado')
                if any('\ufffd' in c for c in cells): reasons.append('El archivo contiene caracteres ilegibles')
                if any(cells[10:]): reasons.append('Existen valores en columnas sin encabezado')
                registro = dict(placa=placa, propietario=nombre, telefono=telefono, marca_modelo=marca, color=color,
                    direccion=direccion, observaciones='\n'.join(notes), revisar=bool(reasons),
                    clave_importacion=hashlib.sha256(f'{digest}:{sheet.title}:{number}'.encode()).hexdigest(),
                    origen={'archivo':path.name, 'sha256':digest, 'hoja':sheet.title, 'fila':number,
                            'celdas':{get_column_letter(i+1):texto(v) for i,v in enumerate(raw)}, 'revision':reasons})
                registros.append(registro)
    finally:
        workbook.close()
    counts = Counter(r['placa'] for r in registros if r['placa'])
    for r in registros:
        if r['placa'] and counts[r['placa']] > 1:
            r['revisar'] = True
            r['origen']['revision'].append('Placa repetida en el archivo; se conserva cada registro original')
        if r['origen']['revision']:
            r['observaciones'] = '\n'.join(filter(None, [r['observaciones'], *r['origen']['revision']]))
    return registros, {'sha256':digest, 'registros':len(registros), 'por_hoja':dict(Counter(r['origen']['hoja'] for r in registros)),
                       'revisar':sum(r['revisar'] for r in registros), 'placas_repetidas':sum(n>1 for n in counts.values()), 'filas_sin_datos':len(omitidas)}
