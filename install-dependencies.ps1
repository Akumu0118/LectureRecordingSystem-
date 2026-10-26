# Windows dependency bootstrap. Run from any directory; paths follow this script.
[CmdletBinding()]
param(
    [switch]$InstallTools,
    [switch]$CheckOnly
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$projectRoot = $PSScriptRoot
$backendPath = Join-Path $projectRoot 'backend'
$frontendPath = Join-Path $projectRoot 'frontend'
$venvPath = Join-Path $backendPath '.venv'
$venvPython = Join-Path $venvPath 'Scripts\python.exe'

function Refresh-ToolPath {
    # Refresh only this process; do not overwrite the user's persistent PATH.
    $parts = @($env:Path,
        [Environment]::GetEnvironmentVariable('Path', 'Machine'),
        [Environment]::GetEnvironmentVariable('Path', 'User'))
    $env:Path = ($parts | Where-Object { $_ }) -join ';'
}

function Invoke-Native {
    param([string]$Executable, [string[]]$CommandArgs)
    & $Executable @CommandArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed (exit $LASTEXITCODE): $Executable $($CommandArgs -join ' ')"
    }
}

function Find-Python {
    $candidates = @()
    if (Test-Path -LiteralPath $venvPython -PathType Leaf) {
        $candidates += @{ Exe = $venvPython; Prefix = @() }
    }
    $launcher = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($launcher) { $candidates += @{ Exe = $launcher.Source; Prefix = @('-3.13') } }
    $python = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($python -and $python.Source -notlike '*\WindowsApps\*') {
        $candidates += @{ Exe = $python.Source; Prefix = @() }
    }
    foreach ($candidate in $candidates) {
        $exe = $candidate.Exe
        $prefix = $candidate.Prefix
        try {
            $result = & $exe @prefix -c 'import sys; print(sys.version.split()[0])' 2>$null
            if ($LASTEXITCODE -eq 0) {
                $version = [version]([string]$result)
                if ($version.Major -eq 3 -and $version.Minor -ge 11 -and $version.Minor -le 13) {
                    return @{ Exe = $exe; Prefix = $prefix; Version = $version }
                }
            }
        } catch { continue }
    }
    return $null
}

function Find-Node {
    $node = Get-Command node.exe -ErrorAction SilentlyContinue
    $npm = Get-Command npm.cmd -ErrorAction SilentlyContinue
    if (-not $node -or -not $npm) { return $null }
    try {
        $version = [version]((& $node.Source --version).TrimStart('v'))
        if ($LASTEXITCODE -eq 0 -and (
            ($version.Major -eq 20 -and $version.Minor -ge 19) -or
            $version -ge [version]'22.12.0')) {
            return @{ Exe = $node.Source; Npm = $npm.Source; Version = $version }
        }
    } catch { return $null }
    return $null
}

function Find-Postgres {
    $server = Get-Command postgres.exe -ErrorAction SilentlyContinue
    if ($server) { return $server.Source }
    $installRoot = Join-Path $env:ProgramFiles 'PostgreSQL'
    if (Test-Path -LiteralPath $installRoot -PathType Container) {
        foreach ($directory in (Get-ChildItem -LiteralPath $installRoot -Directory | Sort-Object Name -Descending)) {
            $serverPath = Join-Path $directory.FullName 'bin\postgres.exe'
            if (Test-Path -LiteralPath $serverPath -PathType Leaf) { return $serverPath }
        }
    }
    return $null
}

function Install-WinGetTool {
    param([string]$PackageId, [switch]$Interactive)
    $winget = Get-Command winget.exe -ErrorAction SilentlyContinue
    if (-not $winget) { throw 'WinGet is unavailable. Install the system tools using the links in README.md, then rerun.' }
    Write-Host "Installing missing prerequisite: $PackageId"
    $arguments = @('install', '--id', $PackageId, '--exact', '--source', 'winget')
    if ($Interactive) { $arguments += '--interactive' }
    Invoke-Native $winget.Source $arguments
    Refresh-ToolPath
}

try {
    if ($env:OS -ne 'Windows_NT') { throw 'This installer targets Windows. See README.md for the project requirements.' }
    if ($CheckOnly -and $InstallTools) { throw 'Use -CheckOnly or -InstallTools, not both.' }
    foreach ($requiredFile in @(
        (Join-Path $backendPath 'requirements-dev.txt'),
        (Join-Path $backendPath '.env.example'),
        (Join-Path $frontendPath 'package-lock.json'),
        (Join-Path $frontendPath '.env.example'))) {
        if (-not (Test-Path -LiteralPath $requiredFile -PathType Leaf)) {
            throw "Missing project file: $requiredFile. Use a checkout containing the complete backend and frontend."
        }
    }
    Refresh-ToolPath
    if ($InstallTools) {
        if (-not (Find-Python)) { Install-WinGetTool 'Python.Python.3.13' }
        if (-not (Find-Node)) { Install-WinGetTool 'OpenJS.NodeJS.LTS' }
        if (-not (Get-Command ffmpeg.exe -ErrorAction SilentlyContinue) -or
            -not (Get-Command ffprobe.exe -ErrorAction SilentlyContinue)) {
            Install-WinGetTool 'Gyan.FFmpeg'
        }
        if (-not (Find-Postgres)) {
            Write-Host 'Complete the PostgreSQL installer and choose your own administrator password.'
            Install-WinGetTool 'PostgreSQL.PostgreSQL.18' -Interactive
        }
    }

    $pythonTool = Find-Python
    $nodeTool = Find-Node
    $ffmpeg = Get-Command ffmpeg.exe -ErrorAction SilentlyContinue
    $ffprobe = Get-Command ffprobe.exe -ErrorAction SilentlyContinue
    $postgres = Find-Postgres
    $missing = @()
    if (-not $pythonTool) { $missing += 'Python 3.11-3.13 (3.13 recommended)' }
    if (-not $nodeTool) { $missing += 'Node.js compatible with Vite and npm' }
    if (-not $ffmpeg) { $missing += 'FFmpeg on PATH' }
    if (-not $ffprobe) { $missing += 'FFprobe on PATH' }
    if (-not $postgres) { $missing += 'PostgreSQL server installation' }
    if ($missing.Count) {
        throw "Missing prerequisites: $($missing -join ', '). Rerun with -InstallTools, or install them manually and open a fresh terminal. Custom PostgreSQL locations need their bin directory on PATH."
    }
    Write-Host "Python: $($pythonTool.Version); Node: $($nodeTool.Version)"
    Invoke-Native $nodeTool.Npm @('--version')
    Invoke-Native $ffmpeg.Source @('-version')
    Invoke-Native $ffprobe.Source @('-version')
    Invoke-Native $postgres @('--version')
    if ($CheckOnly) {
        Write-Host 'Prerequisites found. No packages, configuration, or database were changed. Database connectivity was not checked.'
        exit 0
    }

    if (Test-Path -LiteralPath $venvPath) {
        if (-not (Test-Path -LiteralPath $venvPython -PathType Leaf) -or
            -not (Test-Path -LiteralPath (Join-Path $venvPath 'pyvenv.cfg') -PathType Leaf)) {
            throw 'backend/.venv exists but is not a complete Windows virtual environment. Inspect it before proceeding.'
        }
        Invoke-Native $venvPython @('-c', 'import sys; sys.exit(0 if (3, 11) <= sys.version_info[:2] < (3, 14) else 1)')
    } else {
        Invoke-Native $pythonTool.Exe (@($pythonTool.Prefix) + @('-m', 'venv', $venvPath))
    }
    Write-Host 'Installing backend packages in backend/.venv...'
    Invoke-Native $venvPython @('-m', 'pip', 'install', '-r', (Join-Path $backendPath 'requirements-dev.txt'))
    Invoke-Native $venvPython @('-m', 'pip', 'check')

    Write-Host 'Installing frontend packages from the lockfile...'
    Push-Location -LiteralPath $frontendPath
    try { Invoke-Native $nodeTool.Npm @('ci') }
    finally { Pop-Location }
    foreach ($directory in @($backendPath, $frontendPath)) {
        $environmentFile = Join-Path $directory '.env'
        if (-not (Test-Path -LiteralPath $environmentFile)) {
            Copy-Item -LiteralPath (Join-Path $directory '.env.example') -Destination $environmentFile
            Write-Host "Created configuration template: $environmentFile"
        }
    }
    Write-Host 'Dependencies installed. Existing .env files were preserved.'
    Write-Host 'Next: create your local database, edit backend/.env, run Alembic migrations, then start both servers. Follow README.md.'
    Write-Host 'No database, user/password, migration, or application data was created or changed.'
    exit 0
} catch {
    Write-Host "Setup failed: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
