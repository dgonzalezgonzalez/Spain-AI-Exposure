@echo off
setlocal

cd /d "%~dp0"
title Lanzador dashboard SEPE

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
set "DASHBOARD_URL=http://127.0.0.1:8501"

powershell -NoProfile -Command "try { $r = Invoke-WebRequest -Uri 'http://127.0.0.1:8501/_stcore/health' -UseBasicParsing -TimeoutSec 2; if ($r.StatusCode -eq 200) { exit 0 } else { exit 1 } } catch { exit 1 }"
if "%ERRORLEVEL%"=="0" (
    start "" "%DASHBOARD_URL%"
    exit /b 0
)

echo Arrancando dashboard de Streamlit...
start "SEPE Dashboard" cmd /k "cd /d ""%~dp0"" && ""%PYTHON_EXE%"" -m streamlit run app.py --server.headless true --server.port 8501"

powershell -NoProfile -Command "$url = 'http://127.0.0.1:8501/_stcore/health'; for ($i = 0; $i -lt 60; $i++) { try { $r = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 2; if ($r.StatusCode -eq 200) { exit 0 } } catch {} Start-Sleep -Seconds 1 }; exit 1"
if not "%ERRORLEVEL%"=="0" (
    echo No se pudo levantar el dashboard automaticamente.
    echo Si la ventana de Streamlit muestra un error, corrigelo y vuelve a intentarlo.
    pause
    exit /b 1
)

start "" "%DASHBOARD_URL%"
exit /b 0
