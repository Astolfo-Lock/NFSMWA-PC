@echo off
setlocal EnableExtensions EnableDelayedExpansion
title Compilar importer
cd /d "%~dp0"
set "HERE=%CD%"
for %%P in ("%HERE%\..") do set "PARENT=%%~fP"
set "SIMPLE=%PARENT%\ExeSimple"
set "SPEC=%HERE%\NFSMW Asset Importer.spec"
set "EXE=%HERE%\dist\NFSMW Asset Importer.exe"
set "REQ=%HERE%\requirements.txt"
set "TESTS=%HERE%\tests\test_asset_importer.py"
set "PYTHON="
set "ANYPY="

echo ============================================
echo  Compilar importer
echo  Los EXE listos iran a ExeSimple
echo ============================================
echo.

if not exist "%SPEC%" (
  echo No esta el spec del importador en: %SPEC%
  goto :fail
)

echo Buscando .venv en esta carpeta...
if exist "%HERE%\.venv\Scripts\python.exe" (
  set "PYTHON=%HERE%\.venv\Scripts\python.exe"
  echo .venv: !PYTHON!
  goto :got_python
)

echo Buscando .venv en subcarpetas...
for /d %%D in ("%HERE%\*") do (
  if exist "%%~fD\.venv\Scripts\python.exe" (
    set "PYTHON=%%~fD\.venv\Scripts\python.exe"
    echo .venv cercano: !PYTHON!
    goto :got_python
  )
)

echo Buscando .venv en carpetas cercanas...
if exist "%PARENT%\.venv\Scripts\python.exe" (
  set "PYTHON=%PARENT%\.venv\Scripts\python.exe"
  echo .venv cercano: !PYTHON!
  goto :got_python
)
for /d %%D in ("%PARENT%\*") do (
  if exist "%%~fD\.venv\Scripts\python.exe" (
    set "PYTHON=%%~fD\.venv\Scripts\python.exe"
    echo .venv cercano: !PYTHON!
    goto :got_python
  )
)
for %%P in ("%PARENT%\..") do set "GRAND=%%~fP"
if exist "%GRAND%\.venv\Scripts\python.exe" (
  set "PYTHON=%GRAND%\.venv\Scripts\python.exe"
  echo .venv cercano: !PYTHON!
  goto :got_python
)

echo No hay .venv cercano. Buscando Python del sistema con PyQt6 y PyInstaller...
call :FindSystemWithDeps
if defined PYTHON (
  echo Python del sistema: %PYTHON%
  goto :got_python
)

echo No hay un Python del sistema con esas dependencias. Se creara un .venv.
call :CreateVenv
if not defined PYTHON goto :fail

:got_python
if not exist "%PYTHON%" (
  echo No se encontro python.exe.
  goto :fail
)

echo Python: %PYTHON%
call :EnsureDeps
if not defined PYTHON goto :fail

if exist "%TESTS%" (
  echo.
  echo Ejecutando pruebas...
  "%PYTHON%" -m unittest tests.test_asset_importer -q
  if errorlevel 1 (
    echo Fallaron las pruebas del importador.
    goto :fail
  )
)

echo.
"%PYTHON%" -m PyInstaller --noconfirm --clean "%SPEC%"
if errorlevel 1 (
  echo Fallo la compilacion del NFSMW Asset Importer.
  goto :fail
)

if not exist "%EXE%" (
  echo No se genero el EXE: %EXE%
  goto :fail
)

echo Creado: %EXE%
if not exist "%SIMPLE%" mkdir "%SIMPLE%"
copy /Y "%EXE%" "%SIMPLE%\" >nul
if errorlevel 1 (
  echo No se pudo copiar a ExeSimple.
  goto :fail
)
echo Copia facil: %SIMPLE%\NFSMW Asset Importer.exe
echo.
echo Listo.
pause
exit /b 0

:fail
echo.
pause
exit /b 1

:FindSystemWithDeps
set "PYTHON="
where py >nul 2>&1
if not errorlevel 1 (
  py -3.10 -c "import PyQt6, PyInstaller" >nul 2>&1
  if not errorlevel 1 (
    for /f "delims=" %%E in ('py -3.10 -c "import sys; print(sys.executable)" 2^>nul') do set "PYTHON=%%E"
    if defined PYTHON goto :eof
  )
  py -3 -c "import PyQt6, PyInstaller" >nul 2>&1
  if not errorlevel 1 (
    for /f "delims=" %%E in ('py -3 -c "import sys; print(sys.executable)" 2^>nul') do set "PYTHON=%%E"
    if defined PYTHON goto :eof
  )
)
for /f "delims=" %%P in ('where python 2^>nul') do call :TryPyExe "%%P"
if defined PYTHON goto :eof
for /f "delims=" %%P in ('where python3 2^>nul') do call :TryPyExe "%%P"
if defined PYTHON goto :eof
for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*") do call :TryPyExe "%%D\python.exe"
if defined PYTHON goto :eof
for /d %%D in ("%ProgramFiles%\Python3*") do call :TryPyExe "%%D\python.exe"
if defined PYTHON goto :eof
set "PF86=%ProgramFiles(x86)%"
if defined PF86 (
  for /d %%D in ("%PF86%\Python3*") do call :TryPyExe "%%D\python.exe"
)
if defined PYTHON goto :eof
for /d %%D in ("C:\Python3*") do call :TryPyExe "%%D\python.exe"
goto :eof

:TryPyExe
if defined PYTHON goto :eof
if "%~1"=="" goto :eof
echo %~1 | find /i "\WindowsApps\" >nul
if not errorlevel 1 goto :eof
if not exist "%~1" goto :eof
"%~1" -c "import PyQt6, PyInstaller" >nul 2>&1
if not errorlevel 1 set "PYTHON=%~1"
goto :eof

:FindAnyPython
set "ANYPY="
where py >nul 2>&1
if not errorlevel 1 (
  set "ANYPY=py"
  goto :eof
)
for /f "delims=" %%P in ('where python 2^>nul') do call :TryAnyPy "%%P"
if defined ANYPY goto :eof
for /f "delims=" %%P in ('where python3 2^>nul') do call :TryAnyPy "%%P"
if defined ANYPY goto :eof
for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python3*") do call :TryAnyPy "%%D\python.exe"
if defined ANYPY goto :eof
for /d %%D in ("%ProgramFiles%\Python3*") do call :TryAnyPy "%%D\python.exe"
if defined ANYPY goto :eof
set "PF86=%ProgramFiles(x86)%"
if defined PF86 (
  for /d %%D in ("%PF86%\Python3*") do call :TryAnyPy "%%D\python.exe"
)
if defined ANYPY goto :eof
for /d %%D in ("C:\Python3*") do call :TryAnyPy "%%D\python.exe"
goto :eof

:TryAnyPy
if defined ANYPY goto :eof
if "%~1"=="" goto :eof
echo %~1 | find /i "\WindowsApps\" >nul
if not errorlevel 1 goto :eof
if not exist "%~1" goto :eof
"%~1" -c "import sys" >nul 2>&1
if not errorlevel 1 set "ANYPY=%~1"
goto :eof

:CreateVenv
set "PYTHON="
set "VENVDIR=%HERE%\.venv"
call :FindAnyPython
if not defined ANYPY (
  echo No hay Python. Instala Python 3.10 y vuelve a ejecutar Compilar importer.bat
  goto :eof
)
echo No hay .venv. Creando uno en %VENVDIR% ...
if /i "%ANYPY%"=="py" (
  py -3.10 -m venv "%VENVDIR%"
  if errorlevel 1 py -3 -m venv "%VENVDIR%"
) else (
  "%ANYPY%" -m venv "%VENVDIR%"
)
if not exist "%VENVDIR%\Scripts\python.exe" (
  echo No se pudo crear el .venv.
  goto :eof
)
set "PYTHON=%VENVDIR%\Scripts\python.exe"
goto :eof

:EnsureDeps
"%PYTHON%" -c "import PyQt6, PyInstaller" >nul 2>&1
if not errorlevel 1 (
  echo Dependencias OK: PyQt6, PyInstaller
  goto :eof
)
echo Faltan PyQt6/PyInstaller. Instalando...
if exist "%REQ%" (
  "%PYTHON%" -m pip install -r "%REQ%"
) else (
  "%PYTHON%" -m pip install PyQt6 PyInstaller
)
if errorlevel 1 (
  echo Fallo pip install (hace falta PyQt6 y PyInstaller^).
  set "PYTHON="
  goto :eof
)
"%PYTHON%" -c "import PyQt6, PyInstaller" >nul 2>&1
if errorlevel 1 (
  echo Python no puede importar PyQt6 y PyInstaller.
  set "PYTHON="
)
goto :eof
