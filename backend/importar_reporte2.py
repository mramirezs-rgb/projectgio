import os
import re
import unicodedata
import pandas as pd
import django
from django.utils.dateparse import parse_datetime
from django.utils import timezone

# 1. Configurar entorno Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
try:
    django.setup()
except Exception:
    os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
    try:
        django.setup()
    except Exception as e:
        print(f"Error al iniciar Django: {e}")
        exit()

from django.apps import apps
from django.contrib.auth import get_user_model

# 2. Buscar Modelo Incidente
Incidente = None
for model in apps.get_models():
    if model.__name__ in ['Incidente', 'IncidenteRed']:
        Incidente = model
        break

if not Incidente:
    print("❌ ERROR: No se encontró el modelo de Incidentes.")
    exit()

User = get_user_model()

def normalizar_cadena(texto):
    if not texto or pd.isna(texto):
        return ""
    s = unicodedata.normalize('NFD', str(texto)).encode('ascii', 'ignore').decode("utf-8")
    return s.strip().upper()

def vaciar_base_de_datos():
    print("==================================================")
    print(" 🧹 INICIANDO LIMPIEZA DE LA BASE DE DATOS")
    print("==================================================")
    
    num_incidentes, _ = Incidente.objects.all().delete()
    print(f"-> Incidentes eliminados: {num_incidentes}")

    num_tecnicos, _ = User.objects.filter(is_superuser=False, is_staff=False).delete()
    print(f"-> Usuarios técnicos anteriores eliminados: {num_tecnicos}")
    print("==================================================\n")

def generar_datos_usuario(nombre_completo):
    s = unicodedata.normalize('NFD', nombre_completo).encode('ascii', 'ignore').decode("utf-8")
    partes = s.lower().split()
    
    if len(partes) >= 2:
        username = f"{partes[0]}.{partes[-1]}"
    else:
        username = partes[0] if partes else "tecnico"
        
    clean_name = re.sub(r'[^a-zA-Z0-9]', '', s).upper()
    expediente = f"EXP-{clean_name[:15]}"
    
    return username, expediente

def obtener_o_crear_tecnico(nombre_tecnico):
    if not nombre_tecnico or str(nombre_tecnico).strip().lower() in ['', 'nan', 'none']:
        return None

    nombre_tecnico = str(nombre_tecnico).strip()
    primer_nombre = nombre_tecnico.split()[0]
    
    usuario_existente = User.objects.filter(first_name__icontains=primer_nombre).first()
    if usuario_existente:
        return usuario_existente

    username, expediente = generar_datos_usuario(nombre_tecnico)
    
    i = 1
    u_base, e_base = username, expediente
    while User.objects.filter(username=username).exists():
        username = f"{u_base}{i}"
        i += 1

    i = 1
    while User.objects.filter(expediente=expediente).exists():
        expediente = f"{e_base[:16]}_{i}"
        i += 1

    usuario = User.objects.create(
        username=username,
        first_name=nombre_tecnico,
        last_name="",
        email="",
        expediente=expediente,
        rol='TECNICO',
        is_active=True,
        is_staff=False,
        is_superuser=False
    )
    return usuario

def cargar_csv():
    archivo_path = 'REPORTE2.csv'
    if not os.path.exists(archivo_path):
        print(f"❌ Error: No se encontró el archivo '{archivo_path}'.")
        return

    # Leer CSV buscando la fila real de cabeceras
    raw_df = pd.read_csv(archivo_path, encoding='utf-8', header=None).fillna('')
    
    header_idx = 0
    for i, row in raw_df.iterrows():
        row_str = " ".join([str(val).upper() for val in row.values])
        if 'FOLIO' in row_str or 'INCIDENTE' in row_str:
            header_idx = i
            break
            
    df = raw_df.iloc[header_idx + 1:].copy()
    df.columns = [normalizar_cadena(c) for c in raw_df.iloc[header_idx]]

    print("🔍 DIAGNÓSTICO DE COLUMNAS ENCONTRADAS EN CSV:")
    print("--------------------------------------------------")
    print(list(df.columns))
    print("--------------------------------------------------\n")

    # Identificar columna de Área en el CSV
    col_area = None
    for col in df.columns:
        if 'AREA' in col or 'ZONA' in col or 'SECTOR' in col:
            col_area = col
            break
            
    print(f"📌 Columna detectada para Área en CSV: [{col_area if col_area else 'NO DETECTADA'}]")

    # Diagnóstico del Modelo Incidente en Django
    campos_modelo = {f.name: f for f in Incidente._meta.get_fields()}
    
    campo_area_modelo = None
    for posible in ['area_operativa', 'area', 'area_atencion', 'area_responsable', 'coordinacion']:
        if posible in campos_modelo:
            campo_area_modelo = posible
            break

    print(f"📌 Campo destino detectado en BD Django: [{campo_area_modelo if campo_area_modelo else 'NINGUNO'}]\n")

    vaciar_base_de_datos()

    # Normalizar folios y eliminar duplicados
    if 'FOLIO' in df.columns:
        df['FOLIO'] = df['FOLIO'].astype(str).str.strip()
        df['FOLIO'] = df['FOLIO'].apply(lambda x: x[:-2] if x.endswith('.0') else x)
        df = df[~df['FOLIO'].isin(['', 'NAN', 'NONE'])]
        df = df.drop_duplicates(subset=['FOLIO'], keep='last')

    procesados = 0

    for idx, row in df.iterrows():
        folio = str(row.get('FOLIO', '')).strip()
        if not folio:
            continue

        # Extraer valor del área
        area_val = ""
        if col_area and col_area in row:
            area_val = str(row.get(col_area, '')).strip().upper()
        else:
            for col in row.index:
                if 'AREA' in col:
                    area_val = str(row[col]).strip().upper()
                    if area_val:
                        break

        nombre_tecnico = str(row.get('TECNICO ASIGNADO', row.get('TECNICO', ''))).strip()
        tecnico_obj = obtener_o_crear_tecnico(nombre_tecnico)

        empresa_val = str(row.get('EMPRESA', '')).strip() or 'SIN EMPRESA'
        estatus_io_val = str(row.get('ESTATUS I/O', row.get('ESTATUS', ''))).strip() or 'ABIERTO'
        central_val = str(row.get('CENTRAL', row.get('COPE', ''))).strip() or 'SIN CENTRAL'
        obs_val = str(row.get('OBS USUARIO', row.get('OBSERVACIONES SISA', ''))).strip()

        try:
            dilacion_val = int(float(row.get('DILACION DIAS', row.get('DILACION', 0))))
        except (ValueError, TypeError):
            dilacion_val = 0

        fecha_ingreso_raw = str(row.get('FECHA INGRESO', '')).strip()
        fecha_ingreso_val = parse_datetime(fecha_ingreso_raw) if fecha_ingreso_raw else None
        if fecha_ingreso_val and timezone.is_naive(fecha_ingreso_val):
            fecha_ingreso_val = timezone.make_aware(fecha_ingreso_val)

        raw_datos = {
            'folio': folio,
            'incidente': str(row.get('INCIDENTE', '')).strip(),
            'empresa': empresa_val,
            'referencia': str(row.get('REFERENCIA', '')).strip(),
            'tipo_servicio': str(row.get('TIPO SERVICIO', '')).strip(),
            'ctro_trabajo': str(row.get('CTRO TRABAJO', '')).strip(),
            'telefono_tecnico': str(row.get('TELEFONO TECNICO', '')).strip(),
            'punta_a': str(row.get('PUNTA A', '')).strip(),
            'dir_pta_a': str(row.get('DIR PTA A', '')).strip(),
            'ips': str(row.get('IPS', '')).strip(),
            'dslam': str(row.get('DSLAM', '')).strip(),
            'cope': str(row.get('COPE', '')).strip(),
            'central': central_val,
            'red_secundaria': str(row.get('RED SECUNDARIA', '')).strip(),
            'estatus_io': estatus_io_val,
            'estatus_qp': str(row.get('ESTATUS QP', '')).strip() or 'DESCONOCIDO',
            'fecha_ingreso': fecha_ingreso_val,
            'dilacion': dilacion_val,
            'dilacion_dias': dilacion_val,
            'cve_liq': str(row.get('CVE LIQ', '')).strip(),
            'desc_liq': str(row.get('DESC LIQ', '')).strip(),
            'oqu': str(row.get('OQU', '')).strip(),
            'desc_f1': str(row.get('DESC F1', '')).strip(),
            'desc_cod4': str(row.get('DESC COD4', '')).strip(),
            'desc_carls': str(row.get('DESC CARLS', '')).strip(),
            'desc_cod5': str(row.get('DESC COD5', '')).strip(),
            'obs_usuario': obs_val,
            'observaciones_sisa': str(row.get('OBSERVACIONES SISA', '')).strip(),
            'leyenda_sisa': str(row.get('LEYENDA SISA', '')).strip(),
            'actualizado_por_gio': False,
            'tecnico': tecnico_obj
        }

        # Manejo de ForeignKey o CharField para el campo Área
        if campo_area_modelo:
            field_obj = campos_modelo[campo_area_modelo]
            if field_obj.is_relation and field_obj.many_to_one:
                TargetModel = field_obj.related_model
                if area_val:
                    area_inst, _ = TargetModel.objects.get_or_create(nombre=area_val)
                    raw_datos[campo_area_modelo] = area_inst
            else:
                raw_datos[campo_area_modelo] = area_val

        datos = {k: v for k, v in raw_datos.items() if k in campos_modelo}

        Incidente.objects.update_or_create(folio=folio, defaults=datos)
        
        if procesados < 3:
            print(f"-> Muestra [{folio}]: ÁREA asignada = '{area_val}' (Guardado en campo '{campo_area_modelo}')")

        procesados += 1

    print("\n==================================================")
    print(f" ¡IMPORTACIÓN COMPLETADA EXITOSAMENTE!")
    print(f" -> Total de folios importados: {procesados}")
    print("==================================================")

if __name__ == '__main__':
    cargar_csv()