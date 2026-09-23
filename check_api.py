import os
import sys
import django

DIR_ACTUAL = os.path.dirname(os.path.abspath(__file__))
RUTA_BACKEND = os.path.join(DIR_ACTUAL, 'backend')
if os.path.exists(RUTA_BACKEND) and RUTA_BACKEND not in sys.path:
    sys.path.insert(0, RUTA_BACKEND)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from gio_app.models import Incidente
from usuarios.models import UsuarioGIO

print("=== DIAGNÓSTICO DE FILTROS ===")

# 1. Revisar áreas registradas en los incidentes
areas_incidentes = list(Incidente.objects.values_list('area_operativa', flat=True).distinct())
print(f"\nÁreas presentes en los 633 incidentes: {areas_incidentes}")

# 2. Revisar el usuario 'jefa' o los usuarios registrados
print("\nUsuarios en la base de datos:")
for u in UsuarioGIO.objects.all():
    area_user = getattr(u, 'area', getattr(u, 'area_operativa', 'Sin área'))
    rol_user = getattr(u, 'rol', 'Sin rol')
    print(f" - Usuario: {u.username} | Rol: {rol_user} | Área asignada: {area_user}")

# 3. Conteo de estatus
estatus_list = list(Incidente.objects.values_list('estatus_io', flat=True).distinct())
print(f"\nEstatus presentes en los incidentes: {estatus_list}")