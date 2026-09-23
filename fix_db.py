import os
import sys
import django

# Configurar Django
DIR_ACTUAL = os.path.dirname(os.path.abspath(__file__))
RUTA_BACKEND = os.path.join(DIR_ACTUAL, 'backend')
if os.path.exists(RUTA_BACKEND) and RUTA_BACKEND not in sys.path:
    sys.path.insert(0, RUTA_BACKEND)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from django.db import connection

sql_script = """
DO $$ 
BEGIN 
    -- Quitar NOT NULL y asignar default 0 a 'dilacion' si existe
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name='incidentes_red' AND column_name='dilacion'
    ) THEN
        ALTER TABLE incidentes_red ALTER COLUMN dilacion DROP NOT NULL;
        ALTER TABLE incidentes_red ALTER COLUMN dilacion SET DEFAULT 0;
        UPDATE incidentes_red SET dilacion = 0 WHERE dilacion IS NULL;
    END IF;

    -- Quitar NOT NULL y asignar default 0 a 'dilacion_dias' si existe
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name='incidentes_red' AND column_name='dilacion_dias'
    ) THEN
        ALTER TABLE incidentes_red ALTER COLUMN dilacion_dias DROP NOT NULL;
        ALTER TABLE incidentes_red ALTER COLUMN dilacion_dias SET DEFAULT 0;
        UPDATE incidentes_red SET dilacion_dias = 0 WHERE dilacion_dias IS NULL;
    END IF;
END $$;
"""

print("Corrigiendo restricciones de 'dilacion' en PostgreSQL...")

with connection.cursor() as cursor:
    cursor.execute(sql_script)

print("¡Restricciones actualizadas exitosamente!")