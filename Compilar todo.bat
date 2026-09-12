@echo off
setlocal
cd /d "%~dp0"
echo ============================================
echo  Compilando launcher e importer
echo  Los EXE listos iran a ExeSimple
echo ============================================
echo.

echo --- Launcher ---
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Launcher\build_launcher.ps1"
if errorlevel 1 (
  echo Fallo el launcher.
  pause
  exit /b 1
)

echo.
echo --- Importer ---
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Importer\build_importer.ps1"
if errorlevel 1 (
  echo Fallo el importer.
  pause
  exit /b 1
)

echo.
echo Listo. Abre la carpeta ExeSimple.
explorer "%~dp0ExeSimple"
pause
