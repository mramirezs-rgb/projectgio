@echo off
rem Sincroniza GIO con SISA: lee los reportes nuevos de sisa_imports y deja el archivo de retorno
rem en sisa_exports. Pensado para el Programador de tareas de Windows, cada 15 minutos.
rem Lo que hace cada corrida queda en backend\logs\sisa.log.
setlocal
cd /d "%~dp0.."
set PYTHONUTF8=1
if not exist logs mkdir logs
echo ==== %date% %time% >> logs\sisa.log
".venv\Scripts\python.exe" manage.py ingesta_sisa >> logs\sisa.log 2>&1
".venv\Scripts\python.exe" manage.py exportar_sisa >> logs\sisa.log 2>&1
