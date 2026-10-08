param(
    [string]$InstallPath = "$env:ProgramFiles\NEXLINK"
)
$ErrorActionPreference = 'Stop'

Write-Host "NEXLINK server bootstrap"

# Start an already-installed PostgreSQL Windows service when present.
$postgres = Get-Service -Name 'postgresql*' -ErrorAction SilentlyContinue
if ($postgres) {
    foreach ($service in $postgres) {
        if ($service.Status -ne 'Running') {
            try { Start-Service -Name $service.Name -ErrorAction Stop } catch { Write-Host "PostgreSQL service could not be started: $($_.Exception.Message)" }
        }
    }
}

# Docker Desktop is optional when a working PostgreSQL installation exists.
# If it is installed but stopped, start it so NEXLINK Server can use its isolated
# PostgreSQL fallback on port 55432.
$dockerDesktop = @(
    "$env:ProgramFiles\Docker\Docker\Docker Desktop.exe",
    "$env:LOCALAPPDATA\Programs\Docker\Docker\Docker Desktop.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1
if ($dockerDesktop) {
    $docker = Get-Command docker -ErrorAction SilentlyContinue
    if ($docker) {
        try {
            docker info *> $null
        } catch {
            Start-Process -FilePath $dockerDesktop | Out-Null
        }
    }
}

# The NEXLINK executable performs the final DB connectivity check, migration,
# Docker compose fallback and firewall setup. Keeping this bootstrap lightweight
# makes an installed PostgreSQL deployment work without Docker Desktop.
Write-Host "Infrastructure bootstrap complete. NEXLINK Server will finish setup on first launch."
