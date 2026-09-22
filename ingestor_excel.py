import os
import sys
import glob
import django
import pandas as pd
import unicodedata
import re

# 1. Configurar rutas
DIR_ACTUAL = os.path.dirname(os.path.abspath(__file__))
RUTA_BACKEND = os.path.join(DIR_ACTUAL, 'backend')

if os.path.exists(RUTA_BACKEND) and RUTA_BACKEND not in sys.path:
    sys.path.insert(0, RUTA_BACKEND)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from gio_app.models import Incidente

def normalizar_texto(texto):
    if pd.isna(texto) or texto is None: return ''
    texto = str(texto)
    texto = unicodedata.normalize('NFD', texto).encode('ascii', 'ignore').decode("utf-8")
    return texto.upper().strip()

def limpiar_dataframe(df):
    """Busca dinámicamente la fila de encabezados y elimina la basura superior."""
    header_idx = -1
    
    # Buscar qué fila contiene los títulos reales
    for idx, row in df.head(15).iterrows():
        row_str = ' '.join(str(v).upper() for v in row.values)
        if 'FOLIO' in row_str or 'INCIDENTE' in row_str:
            header_idx = idx
            break

    # Si encuentra los encabezados, recorta el DataFrame
    if header_idx != -1:
        df.columns = df.iloc[header_idx]
        df = df.iloc[header_idx + 1:].reset_index(drop=True)

    # Limpiar los nombres de las columnas
    df.columns = [normalizar_texto(c) for c in df.columns]

    # Separar columnas si todo viene pegado en una sola celda
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
    # Intento 1: HTML disfrazado de XLS (El más común en SISA/QP)
    for enc in ['utf-8', 'latin1', 'cp1252']:
        try:
            tablas = pd.read_html(ruta, encoding=enc)
            if tablas and len(tablas[0]) > 0:
                return limpiar_dataframe(tablas[0])
        except Exception:
            pass

    # Intento 2: Motores de Excel
    for engine in ['xlrd', 'openpyxl', None]:
        try:
            df = pd.read_excel(ruta, engine=engine)
            if df is not None and len(df) > 0:
                return limpiar_dataframe(df)
        except Exception:
            pass
    return None

def buscar_valor(row, lista_claves):
    """Busca el valor exacto usando las claves normalizadas."""
    for clave in lista_claves:
        if clave in row:
            val = str(row[clave]).strip()
            if val and val.lower() not in ['nan', 'none', '—', '--------', 'null', 'n/a']:
                return val
    return None

def es_folio_valido(folio_str):
    if not folio_str:
        return False
    # Evitar que tome direcciones o textos largos como folio por error
    if len(folio_str) > 15 or ' ' in folio_str:
        return False
    if folio_str.isdigit():
        return len(folio_str) >= 5
    return len(folio_str) >= 3

def procesar_archivos():
    archivos = glob.glob('*.xlsx') + glob.glob('*.xls')
    if not archivos:
        print("No se encontraron archivos .xls o .xlsx")
        return

    print("Limpiando registros desfasados de la base de datos...")
    Incidente.objects.all().delete()

    total_creados = 0
    total_actualizados = 0

    for ruta in archivos:
        print(f"\nProcesando: {ruta}...")
        df = cargar_dataframe(ruta)
        
        if df is None:
            print(f"❌ No se pudo extraer la información de '{ruta}'.")
            continue

        for _, row in df.iterrows():
            # Mapear columnas directamente
            folio = buscar_valor(row, ['FOLIO', 'FOLIO SISA'])
            
            if not es_folio_valido(folio):
                continue

            try:
                dilacion_str = buscar_valor(row, ['DILACION DIAS', 'DILACION', 'DILACION  DIAS'])
                dilacion_val = int(float(dilacion_str)) if dilacion_str else 0
            except (ValueError, TypeError):
                dilacion_val = 0

            obj, created = Incidente.objects.update_or_create(
                folio=folio,
                defaults={
                    'incidente': buscar_valor(row, ['INCIDENTE']),
                    'empresa': buscar_valor(row, ['EMPRESA', 'CLIENTE']),
                    'referencia': buscar_valor(row, ['REFERENCIA']),
                    'area_operativa': buscar_valor(row, ['AREA', 'DIVISIONAL', 'REGION', 'AREA OPERATIVA']) or 'PUEBLA',
                    'central': buscar_valor(row, ['CENTRAL', 'COPE', 'CTRO TRABAJO']),
                    'tecnico_asignado': buscar_valor(row, ['TECNICO ASIGNADO', 'TECNICO', 'PROVEEDOR']),
                    'estatus_io': buscar_valor(row, ['ESTATUS I/O', 'ESTATUS TAREA', 'ESTATUS QP', 'ESTATUS']) or 'PENDIENTE',
                    'tipo_servicio': buscar_valor(row, ['TIPO SERVICIO', 'TIPO_SERVICIO', 'CATEGORIA SERVICIO']),
                    'dilacion_dias': dilacion_val,
                    'obs_usuario': buscar_valor(row, ['OBS USUARIO', 'OBSERVACIONES USUARIO', 'OBSERVACIONES SISA']),
                    'actualizado_por_gio': False
                }
            )
            
            if created:
                total_creados += 1
            else:
                total_actualizados += 1

    print(f"\n¡Ingesta completada exitosamente!")
    print(f"Folios nuevos: {total_creados} | Duplicados actualizados: {total_actualizados}")

if __name__ == '__main__':
    procesar_archivos()