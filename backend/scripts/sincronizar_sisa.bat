@echo off
rem Sincroniza GIO con SISA: lee los reportes nuevos de sisa_imports y deja el archivo de retorno
rem en sisa_exports. Pensado para el Programador de tareas de Windows, cada 15 minutos.
rem Lo que hace cada corrida queda en backend\logs\sisa.log.
setlocal
cd /d "%~dp0.."
set PYTHONUTF8=1
if not exist logs mkdir logs
echo ==== %date% %time% >> logs\sisa.log

rem El entorno virtual puede estar en backend\ o en la carpeta del proyecto, con o sin punto.
set "PYTHON=.venv\Scripts\python.exe"
if not exist "%PYTHON%" set "PYTHON=venv\Scripts\python.exe"
if not exist "%PYTHON%" set "PYTHON=..\.venv\Scripts\python.exe"
if not exist "%PYTHON%" set "PYTHON=..\venv\Scripts\python.exe"
if not exist "%PYTHON%" (
  echo No se encontro el entorno virtual de Python: .venv o venv >> logs\sisa.log
  exit /b 1
)

"%PYTHON%" manage.py ingesta_sisa >> logs\sisa.log 2>&1
"%PYTHON%" manage.py exportar_sisa >> logs\sisa.log 2>&1
