$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
Write-Host '=== NEXLINK Windows x64 Build ==='
if (-not (Get-Command python -ErrorAction SilentlyContinue)) { throw 'Python 3.12 is required.' }
$pythonVersion = (python -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")').Trim()
if ($pythonVersion -ne '3.12') { throw "Use Python 3.12 for reproducible Windows builds (found $pythonVersion)." }
$pythonPlatform = (python -c 'import os, struct; print(os.name, struct.calcsize("P") * 8)').Trim()
if ($pythonPlatform -ne 'nt 64') { throw "Use 64-bit Python on Windows (found $pythonPlatform)." }

python -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw 'pip could not be upgraded.' }
python -m pip install -r requirements-windows-build.txt
if ($LASTEXITCODE -ne 0) { throw 'Windows build dependencies could not be installed.' }

python -m compileall -q backend client/windows nexlink_agent nexlink_ai server_gui.py server_launcher.py
if ($LASTEXITCODE -ne 0) { throw 'NEXLINK source compilation failed.' }

Remove-Item -Recurse -Force dist, build -ErrorAction SilentlyContinue
python -m PyInstaller --clean --noconfirm NEXLINK-Server.spec
if ($LASTEXITCODE -ne 0) { throw 'NEXLINK Server packaging failed.' }
python -m PyInstaller --clean --noconfirm client/windows/NEXLINK-Client.spec
if ($LASTEXITCODE -ne 0) { throw 'NEXLINK Client packaging failed.' }

$originalLocalAppData = $env:LOCALAPPDATA
$selfTestLocalAppData = Join-Path $env:TEMP "NEXLINK-build-self-test-$([Guid]::NewGuid().ToString('N'))"
New-Item -ItemType Directory -Path $selfTestLocalAppData -Force | Out-Null
try {
    $env:LOCALAPPDATA = $selfTestLocalAppData
    & dist/NEXLINK-Server/NEXLINK-Server.exe --self-test
    if ($LASTEXITCODE -ne 0) { throw 'NEXLINK Server self-test failed.' }
    & dist/NEXLINK-Client/NEXLINK-Client.exe --self-test
    if ($LASTEXITCODE -ne 0) { throw 'NEXLINK Client self-test failed.' }
}
finally {
    if ($null -eq $originalLocalAppData) {
        Remove-Item Env:LOCALAPPDATA -ErrorAction SilentlyContinue
    } else {
        $env:LOCALAPPDATA = $originalLocalAppData
    }
    Remove-Item -Recurse -Force $selfTestLocalAppData -ErrorAction SilentlyContinue
}

python package_windows.py
if ($LASTEXITCODE -ne 0) { throw 'NEXLINK executable verification or bundle packaging failed.' }

Write-Host 'NEXLINK Windows executables passed PE, bundle, Qt, icon and UI smoke checks.'
Write-Host '  dist/NEXLINK-Windows/Client/NEXLINK-Client.exe'
Write-Host '  dist/NEXLINK-Windows/Server/NEXLINK-Server.exe'
Write-Host '  dist/NEXLINK-Client-Windows.zip'
Write-Host '  dist/NEXLINK-Server-Windows.zip'
Write-Host '  dist/NEXLINK-Windows-Bundle.zip'
