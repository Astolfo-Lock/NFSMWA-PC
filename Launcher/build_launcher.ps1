$ErrorActionPreference = 'Stop'
$LauncherDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Spec = Join-Path $LauncherDir 'Need For Speed Most Wanted Android.spec'

function Get-ParentPath([string]$Path) {
    if ([string]::IsNullOrWhiteSpace($Path)) { return $null }
    $Parent = Split-Path -Parent $Path
    if ([string]::IsNullOrWhiteSpace($Parent) -or $Parent -eq $Path) { return $null }
    return $Parent
}

function Test-VenvPython([string]$Dir) {
    if ([string]::IsNullOrWhiteSpace($Dir)) { return $null }
    $Candidate = Join-Path $Dir '.venv\Scripts\python.exe'
    if (Test-Path -LiteralPath $Candidate) { return $Candidate }
    return $null
}

function Find-ChildVenvPython([string]$Dir) {
    if ([string]::IsNullOrWhiteSpace($Dir) -or -not (Test-Path -LiteralPath $Dir)) { return $null }
    $Children = @(Get-ChildItem -LiteralPath $Dir -Directory -Force -ErrorAction SilentlyContinue | Select-Object -First 40)
    foreach ($Child in $Children) {
        $Hit = Test-VenvPython $Child.FullName
        if ($Hit) { return $Hit }
    }
    return $null
}

function Find-VenvPython([string]$Start) {
    $Hit = Test-VenvPython $Start
    if ($Hit) { return $Hit }
    $Hit = Find-ChildVenvPython $Start
    if ($Hit) { return $Hit }

    $Parent = Get-ParentPath $Start
    if ($Parent) {
        $Hit = Test-VenvPython $Parent
        if ($Hit) { return $Hit }
        $Hit = Find-ChildVenvPython $Parent
        if ($Hit) { return $Hit }

        $Grand = Get-ParentPath $Parent
        if ($Grand) { return (Test-VenvPython $Grand) }
    }
    return $null
}

function Find-PythonLauncher {
    foreach ($Name in @('py', 'python', 'python3')) {
        $Cmd = Get-Command $Name -ErrorAction SilentlyContinue
        if ($Cmd) { return $Cmd.Source }
    }
    return $null
}

function Find-PathPythonWithDeps {
    $Py = Get-Command py -ErrorAction SilentlyContinue
    if ($Py) {
        foreach ($Ver in @('-3.10', '-3')) {
            & $Py.Source $Ver -c "import PyQt6, PyInstaller" 2>$null | Out-Null
            if ($LASTEXITCODE -eq 0) {
                $Exe = & $Py.Source $Ver -c "import sys; print(sys.executable)"
                if ($Exe) { return $Exe.Trim() }
            }
        }
    }
    foreach ($Name in @('python', 'python3')) {
        $Cmd = Get-Command $Name -ErrorAction SilentlyContinue
        if (-not $Cmd) { continue }
        & $Cmd.Source -c "import PyQt6, PyInstaller" 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) { return $Cmd.Source }
    }
    return $null
}

function Ensure-BuildDeps([string]$PythonExe, [string]$Requirements) {
    & $PythonExe -c "import PyQt6, PyInstaller" 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) { return }
    Write-Host "Faltan PyQt6/PyInstaller. Instalando..."
    if ($Requirements -and (Test-Path -LiteralPath $Requirements)) {
        & $PythonExe -m pip install -r $Requirements
    } else {
        & $PythonExe -m pip install PyQt6 PyInstaller
    }
    if ($LASTEXITCODE -ne 0) { throw 'Fallo pip install (hace falta PyQt6 y PyInstaller).' }
    & $PythonExe -c "import PyQt6, PyInstaller" 2>$null | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Python no puede importar PyQt6 y PyInstaller.' }
}

function Copy-ToExeSimple([string]$ExePath) {
    $Bundle = Get-ParentPath $LauncherDir
    if (-not $Bundle) { $Bundle = $LauncherDir }
    $Simple = Join-Path $Bundle 'ExeSimple'
    New-Item -ItemType Directory -Force -Path $Simple | Out-Null
    $Dest = Join-Path $Simple (Split-Path -Leaf $ExePath)
    Copy-Item -Force -LiteralPath $ExePath -Destination $Dest
    Write-Host "Copia facil: $Dest"
}

$PythonExe = Find-VenvPython $LauncherDir
$ProjectRoot = $null
if ($PythonExe) {
    $ProjectRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $PythonExe))
}
if (-not $PythonExe) {
    $PythonExe = Find-PathPythonWithDeps
    if ($PythonExe) { Write-Host "Python del PATH (pip global): $PythonExe" }
}

if (-not $PythonExe) {
    $Launcher = Find-PythonLauncher
    if (-not $Launcher) {
        throw 'No hay Python. Instala Python 3.10 y vuelve a ejecutar Compilar launcher.bat'
    }
    $VenvRoot = Get-ParentPath $LauncherDir
    if (-not $VenvRoot) { $VenvRoot = $LauncherDir }
    $VenvDir = Join-Path $VenvRoot '.venv'
    Write-Host "No hay .venv. Creando uno en $VenvDir ..."
    if ($Launcher -like '*\py.exe') {
        & $Launcher -3.10 -m venv $VenvDir
    } else {
        & $Launcher -m venv $VenvDir
    }
    if ($LASTEXITCODE -ne 0) { throw 'No se pudo crear .venv.' }
    $PythonExe = Join-Path $VenvDir 'Scripts\python.exe'
    $ProjectRoot = $VenvRoot
}

if ([string]::IsNullOrWhiteSpace($PythonExe) -or -not (Test-Path -LiteralPath $PythonExe)) {
    throw 'No se encontro Python.'
}

$Requirements = Join-Path $LauncherDir 'requirements.txt'
if (-not (Test-Path -LiteralPath $Requirements)) {
    $ReqRoot = Get-ParentPath $LauncherDir
    if ($ReqRoot) { $Requirements = Join-Path $ReqRoot 'requirements.txt' }
}
Write-Host "Python: $PythonExe"
Ensure-BuildDeps $PythonExe $Requirements
Set-Location -LiteralPath $LauncherDir
if ($ProjectRoot) { $env:NFSMW_PROJECT_ROOT = $ProjectRoot }
& $PythonExe -m PyInstaller --noconfirm --clean $Spec
if ($LASTEXITCODE -ne 0) { throw 'Fallo la compilacion del launcher.' }

$Exe = Join-Path $LauncherDir 'dist\Need For Speed Most Wanted Android.exe'
if (-not (Test-Path -LiteralPath $Exe)) {
    throw "No se genero el EXE: $Exe"
}

Write-Host "Creado: $Exe"
Copy-ToExeSimple $Exe
