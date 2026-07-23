# install.ps1
# Requires Administrator privileges
param (
    [string]$ServiceUser = "LocalSystem"
)

$ErrorActionPreference = "Stop"

# Get current script directory
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$ProjectRoot = (Resolve-Path "$ScriptDir\..\..").ProviderPath
$BackendDir = "$ProjectRoot\backend"
$PythonExe = "$BackendDir\.venv\Scripts\python.exe"
$ServiceName = "SenoritaBackend"

Write-Host "Installing Senorita OS Windows Service..."

# Ensure python is available
if (-Not (Test-Path $PythonExe)) {
    Write-Error "Python virtual environment not found at $PythonExe. Please set up the backend first."
    exit 1
}

# Check if nssm is installed
$nssm = Get-Command nssm -ErrorAction SilentlyContinue
if (-not $nssm) {
    Write-Host "nssm not found in PATH. Please install nssm (e.g. choco install nssm) and re-run this script."
    exit 1
}

# Stop and remove existing service if present
if (Get-Service -Name $ServiceName -ErrorAction SilentlyContinue) {
    Write-Host "Service $ServiceName already exists. Stopping and removing..."
    Stop-Service -Name $ServiceName -Force
    nssm remove $ServiceName confirm
}

Write-Host "Registering service $ServiceName with nssm..."
nssm install $ServiceName "$PythonExe" "main.py"
nssm set $ServiceName AppDirectory "$BackendDir"

# Restart on failure (KeepAlive)
nssm set $ServiceName AppRestartDelay 2000
nssm set $ServiceName AppExit Default Restart

# Logs
$LogDir = "$ProjectRoot\logs"
if (-Not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir }
nssm set $ServiceName AppStdout "$LogDir\senorita-backend.out.log"
nssm set $ServiceName AppStderr "$LogDir\senorita-backend.err.log"
nssm set $ServiceName AppRotateFiles 1

# Start the service
Write-Host "Starting $ServiceName..."
Start-Service -Name $ServiceName

Write-Host "Señorita backend is now running as a background service."
Write-Host "Logs are located in $LogDir"
