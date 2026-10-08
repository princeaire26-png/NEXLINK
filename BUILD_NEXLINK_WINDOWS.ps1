$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
Write-Host '=== NEXLINK 2.1 Windows Build ==='

$required = @(
    'server_launcher.spec',
    'client/windows/NEXLINK-Client.spec',
    'server_gui.py',
    'client/windows/nexlink_client.py',
    'backend/migrations/postgres/004_nexlink_platform.sql',
    'deployment-compose.server.yml'
)
foreach ($path in $required) {
    if (-not (Test-Path $path)) { throw "Required build file is missing: $path" }
}

if (-not (Get-Command python -ErrorAction SilentlyContinue)) { throw 'Python is required.' }
python -m pip install --upgrade pip
python -m pip install -r backend/requirements.txt
python -m pip install -r client/windows/requirements.txt
python -m pip install pyinstaller

python -m compileall backend client/windows nexlink_agent nexlink_ai server_gui.py server_launcher.py
if ($LASTEXITCODE -ne 0) { throw 'Python source validation failed.' }

Write-Host 'Validating PyInstaller specifications...'
python -m py_compile server_launcher.spec client/windows/NEXLINK-Client.spec
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller specification validation failed.' }

Write-Host 'Building NEXLINK Server...'
pyinstaller --clean --noconfirm server_launcher.spec
if ($LASTEXITCODE -ne 0) { throw 'NEXLINK Server PyInstaller build failed.' }

Write-Host 'Building NEXLINK Client...'
pyinstaller --clean --noconfirm client/windows/NEXLINK-Client.spec
if ($LASTEXITCODE -ne 0) { throw 'NEXLINK Client PyInstaller build failed.' }

New-Item -ItemType Directory -Force -Path dist/client | Out-Null
Copy-Item dist/NEXLINK-Client.exe dist/client/NEXLINK-Client.exe -Force

& dist/NEXLINK-Server.exe --self-test
if ($LASTEXITCODE -ne 0) { throw 'NEXLINK Server self-test failed.' }
& dist/client/NEXLINK-Client.exe --self-test
if ($LASTEXITCODE -ne 0) { throw 'NEXLINK Client self-test failed.' }

$iscc = Get-Command ISCC.exe -ErrorAction SilentlyContinue
if ($iscc) {
    Write-Host 'Compiling native Windows installer with Inno Setup...'
    & $iscc.Source installer/NEXLINK-Setup.iss
    if ($LASTEXITCODE -ne 0) { throw 'NEXLINK Inno Setup build failed.' }
} else {
    Write-Host 'Inno Setup not found; EXEs are built. Install Inno Setup 6 and compile installer/NEXLINK-Setup.iss to create NEXLINK-Setup.exe.'
}

Write-Host ''
Write-Host 'BUILD COMPLETE'
Write-Host '  dist/NEXLINK-Server.exe'
Write-Host '  dist/client/NEXLINK-Client.exe'
Write-Host '  installer-output/NEXLINK-Setup.exe (when Inno Setup is installed)'
