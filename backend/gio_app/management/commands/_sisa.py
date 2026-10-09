import unicodedata

import pandas as pd
from django.utils import timezone

VACIOS = {'', 'NAN', 'NONE', 'NULL', 'N/A', 'NA', '-', '--', '---', '—'}


def normalizar_encabezado(valor):
    texto = unicodedata.normalize('NFD', str(valor)).encode('ascii', 'ignore').decode('utf-8')
    return ' '.join(texto.upper().split())


def texto(valor, maximo=None):
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return ''
    limpio = ' '.join(str(valor).split()).strip()
    if limpio.upper() in VACIOS:
        return ''
    return limpio[:maximo] if maximo else limpio


def primer_valor(fila, claves, maximo=None):
    for clave in claves:
        if clave in fila:
            valor = texto(fila[clave], maximo)
            if valor:
                return valor
    return ''


def entero(valor, defecto=0):
    try:
        return int(float(str(valor).strip()))
    except (TypeError, ValueError):
        return defecto


def limpiar_central(valor):
    limpio = texto(valor).upper()
    if not limpio:
        return ''
    if ' - ' in limpio:
        limpio = limpio.split(' - ', 1)[1].strip()
    for prefijo in ('CT ', 'CENTRAL ', 'COPE '):
        if limpio.startswith(prefijo):
            limpio = limpio[len(prefijo):].strip()
    return limpio


def a_fecha(valor):
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return None
    crudo = texto(valor)
    if not crudo:
        return None
    marca = None
    for formato in ('%Y-%m-%d %H:%M:%S', '%d/%m/%Y %H:%M:%S', '%Y-%m-%d', '%d/%m/%Y'):
        try:
            marca = pd.to_datetime(crudo, format=formato)
            break
        except (ValueError, TypeError):
            marca = None
    if marca is None:
        marca = pd.to_datetime(crudo, dayfirst=True, errors='coerce')
    if marca is None or pd.isna(marca):
        return None
    fecha = marca.to_pydatetime()
    if timezone.is_naive(fecha):
        fecha = timezone.make_aware(fecha, timezone.get_current_timezone())
    return fecha


def leer_tabla(ruta):
    sufijo = ruta.suffix.lower()
    if sufijo in ('.xlsx', '.xls'):
        marcos = []
        for motor in ('openpyxl', 'xlrd', None):
            try:
                marcos.append(pd.read_excel(ruta, dtype=str, engine=motor))
                break
            except Exception:
                continue
        if not marcos:
            try:
                marcos = pd.read_html(ruta)
            except Exception:
                marcos = []
        if not marcos:
            raise ValueError(f'No fue posible leer {ruta.name} como hoja de cálculo.')
        marco = marcos[0]
    else:
        ultimo_error = None
        marco = None
        for codificacion in ('utf-8-sig', 'utf-8', 'latin1', 'cp1252'):
            try:
                marco = pd.read_csv(ruta, dtype=str, encoding=codificacion,
                                    keep_default_na=False, skip_blank_lines=True)
                break
            except (UnicodeDecodeError, ValueError) as error:
                ultimo_error = error
        if marco is None:
            raise ValueError(f'No fue posible decodificar {ruta.name}: {ultimo_error}')

    marco.columns = [normalizar_encabezado(columna) for columna in marco.columns]
    if 'FOLIO' not in marco.columns:
        indice = None
        for posicion in range(min(len(marco), 15)):
            fila = ' '.join(normalizar_encabezado(v) for v in marco.iloc[posicion].tolist())
            if 'FOLIO' in fila.split():
                indice = posicion
                break
        if indice is None:
            raise ValueError(f'{ruta.name} no contiene una columna FOLIO identificable.')
        marco.columns = [normalizar_encabezado(v) for v in marco.iloc[indice].tolist()]
        marco = marco.iloc[indice + 1:].reset_index(drop=True)
    return marco


def folio_valido(folio):
    if not folio or ' ' in folio or len(folio) > 50:
        return False
    if folio.endswith('.0'):
        folio = folio[:-2]
    return len(folio) >= 3


def limpiar_folio(folio):
    folio = texto(folio)
    return folio[:-2] if folio.endswith('.0') else folio
