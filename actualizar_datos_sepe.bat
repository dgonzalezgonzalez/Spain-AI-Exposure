@echo off
setlocal

cd /d "%~dp0"
title Actualizacion de datos SEPE

set "PYTHON_EXE="
for /f "delims=" %%I in ('where python 2^>nul') do (
    set "PYTHON_EXE=%%I"
    goto :python_found
)

echo No se ha encontrado Python en el sistema.
echo Instala Python o revisa la variable PATH.
pause
exit /b 1

:python_found
echo.
echo Verificando si el SEPE ha publicado nuevos datos...
echo.
"%PYTHON_EXE%" run_pipeline.py --workers 10
set "EXIT_CODE=%ERRORLEVEL%"

echo.
if not "%EXIT_CODE%"=="0" (
    echo La actualizacion ha terminado con errores. Revisa los mensajes anteriores.
    pause
    exit /b %EXIT_CODE%
)

echo Actualizacion completada.
pause
