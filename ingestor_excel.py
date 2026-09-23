import os
import sys
import glob
import django
import pandas as pd
import unicodedata
import re

# 1. Configurar rutas para cargar Django
DIR_ACTUAL = os.path.dirname(os.path.abspath(__file__))
RUTA_BACKEND = os.path.join(DIR_ACTUAL, 'backend')

if os.path.exists(RUTA_BACKEND) and RUTA_BACKEND not in sys.path:
    sys.path.insert(0, RUTA_BACKEND)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from gio_app.models import Incidente
from usuarios.models import UsuarioGIO


def normalizar_texto(texto):
    if pd.isna(texto) or texto is None: return ''
    texto = str(texto)
    texto = unicodedata.normalize('NFD', texto).encode('ascii', 'ignore').decode("utf-8")
    return texto.upper().strip()


def mapear_estatus(estatus_raw):
    """Mapea los estatus técnicos (UP/DOWN) a las columnas del Kanban."""
    if not estatus_raw:
        return 'Pendiente'
    
    e = str(estatus_raw).upper().strip()
    
    if 'DOWN' in e or 'ABIERTO' in e or 'FALLA' in e:
        return 'Abierto'
    elif 'UP' in e or 'RESUELTO' in e or 'OK' in e or 'LIQUIDADO' in e:
        return 'Resuelto'
    elif 'ATENCION' in e or 'PROCESO' in e or 'ASIGNADO' in e:
        return 'En Atención'
    elif 'CERRADO' in e or 'CANCELADO' in e:
        return 'Cerrado'
    else:
        return 'Pendiente'


def limpiar_dataframe(df):
    header_idx = -1
    for idx, row in df.head(15).iterrows():
        row_str = ' '.join(str(v).upper() for v in row.values)
        if 'FOLIO' in row_str or 'INCIDENTE' in row_str:
            header_idx = idx
            break

    if header_idx != -1:
        df.columns = df.iloc[header_idx]
        df = df.iloc[header_idx + 1:].reset_index(drop=True)

    df.columns = [normalizar_texto(c) for c in df.columns]

    if len(df.columns) == 1:
        col_name = df.columns[0]
        nuevas_cols = re.split(r' {2,}|\t+', col_name)
        df = df[col_name].astype(str).str.split(r' {2,}|\t+', expand=True)
        for i in range(len(df.columns)):
            if i < len(nuevas_cols):
                df.rename(columns={i: nuevas_cols[i]}, inplace=True)
            else:
                df.rename(columns={i: f"COL_{i}"}, inplace=True)
        df.columns = [normalizar_texto(c) for c in df.columns]

    return df


def cargar_dataframe(ruta):
    for enc in ['utf-8', 'latin1', 'cp1252']:
        try:
            tablas = pd.read_html(ruta, encoding=enc)
            if tablas and len(tablas[0]) > 0:
                return limpiar_dataframe(tablas[0])
        except Exception:
            pass

    for engine in ['xlrd', 'openpyxl', None]:
        try:
            df = pd.read_excel(ruta, engine=engine)
            if df is not None and len(df) > 0:
                return limpiar_dataframe(df)
        except Exception:
            pass
    return None


def buscar_valor(row, lista_claves):
    for clave in lista_claves:
        if clave in row:
            val = str(row[clave]).strip()
            if val and val.lower() not in ['nan', 'none', '—', '--------', 'null', 'n/a']:
                return val
    return None


def es_folio_valido(folio_str):
    if not folio_str:
        return False
    if len(folio_str) > 15 or ' ' in folio_str:
        return False
    if folio_str.isdigit():
        return len(folio_str) >= 5
    return len(folio_str) >= 3


def procesar_archivos():
    archivos = glob.glob('*.xlsx') + glob.glob('*.xls')
    if not archivos:
        print("❌ No se encontraron archivos .xls o .xlsx.")
        return

    print("Limpiando registros antiguos...")
    Incidente.objects.all().delete()

    # Normalizar áreas de los usuarios a Mayúsculas
    for u in UsuarioGIO.objects.all():
        if hasattr(u, 'area') and u.area:
            u.area = u.area.upper()
            u.save()

    total_creados = 0

    for ruta in archivos:
        print(f"Procesando: {ruta}...")
        df = cargar_dataframe(ruta)
        if df is None: continue

        for _, row in df.iterrows():
            folio = buscar_valor(row, ['FOLIO', 'FOLIO SISA'])
            if not es_folio_valido(folio): continue

            try:
                dilacion_str = buscar_valor(row, ['DILACION DIAS', 'DILACION', 'DILACION  DIAS'])
                dilacion_val = int(float(dilacion_str)) if dilacion_str else 0
            except (ValueError, TypeError):
                dilacion_val = 0

            tecnico_str = buscar_valor(row, ['TECNICO ASIGNADO', 'TECNICO', 'PROVEEDOR'])
            tecnico_obj = None
            if tecnico_str:
                tecnico_obj = UsuarioGIO.objects.filter(expediente=tecnico_str).first() or \
                              UsuarioGIO.objects.filter(username=tecnico_str).first()

            estatus_raw = buscar_valor(row, ['ESTATUS I/O', 'ESTATUS TAREA', 'ESTATUS QP', 'ESTATUS'])
            estatus_kanban = mapear_estatus(estatus_raw)

            area_raw = buscar_valor(row, ['AREA', 'DIVISIONAL', 'REGION', 'AREA OPERATIVA']) or 'PUEBLA'

            defaults_data = {
                'incidente': buscar_valor(row, ['INCIDENTE']),
                'empresa': buscar_valor(row, ['EMPRESA', 'CLIENTE']),
                'referencia': buscar_valor(row, ['REFERENCIA']),
                'area_operativa': area_raw.upper(),
                'central': buscar_valor(row, ['CENTRAL', 'COPE', 'CTRO TRABAJO']) or 'SIN CENTRAL',
                'tecnico': tecnico_obj,
                'estatus_io': estatus_kanban,
                'tipo_servicio': buscar_valor(row, ['TIPO SERVICIO', 'TIPO_SERVICIO', 'CATEGORIA SERVICIO']),
                'dilacion_dias': dilacion_val,
                'obs_usuario': buscar_valor(row, ['OBS USUARIO', 'OBSERVACIONES USUARIO', 'OBSERVACIONES SISA']),
                'actualizado_por_gio': False
            }

            if hasattr(Incidente, 'dilacion'):
                defaults_data['dilacion'] = dilacion_val

            Incidente.objects.update_or_create(folio=folio, defaults=defaults_data)
            total_creados += 1

    print(f"\n¡Ingesta completada! Se cargaron {total_creados} folios con estatus del Kanban.")


if __name__ == '__main__':
    procesar_archivos()