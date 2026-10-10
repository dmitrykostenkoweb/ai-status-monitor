# Windows entry point for ai-cli-status-monitor.
#
#   From a checkout:  powershell -ExecutionPolicy Bypass -File install.ps1
#   Without one:      irm https://raw.githubusercontent.com/dmitrykostenkoweb/ai-status-monitor/main/install.ps1 | iex
#
# The installer itself is install.py; this wrapper finds Python and, when run
# without a checkout, clones the repository into the managed source directory.
# Everything runs inside a script block so that `irm | iex` neither closes the
# user's PowerShell window nor leaves settings behind in their session.
$aiStatusExitCode = & {
    $ErrorActionPreference = 'Stop'

    function Find-Python {
        # The leading comma keeps one-element arrays from being unrolled into a string.
        if ($env:AI_STATUS_PYTHON) { return ,@($env:AI_STATUS_PYTHON) }
        if (Get-Command py -ErrorAction SilentlyContinue) { return ,@('py', '-3') }
        if (Get-Command python -ErrorAction SilentlyContinue) { return ,@('python') }
        throw 'Python 3.9+ is required. Install it from https://www.python.org/downloads/ (tick "Add python.exe to PATH").'
    }

    $python = @(Find-Python)
    $projectDir = if ($PSScriptRoot) { $PSScriptRoot } else { '' }

    if (-not $projectDir -or -not (Test-Path (Join-Path $projectDir 'install.py'))) {
        $repo = if ($env:AI_STATUS_UPDATE_REPO) { $env:AI_STATUS_UPDATE_REPO } else { 'dmitrykostenkoweb/ai-status-monitor' }
        $branch = if ($env:AI_STATUS_UPDATE_BRANCH) { $env:AI_STATUS_UPDATE_BRANCH } else { 'main' }
        $dataDir = if ($env:AI_STATUS_DATA_DIR) { $env:AI_STATUS_DATA_DIR } else { Join-Path $env:LOCALAPPDATA 'ai-cli-status-monitor\data' }
        $projectDir = Join-Path $dataDir 'src'
        if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
            throw 'git is required to install without a checkout. Install Git for Windows and try again.'
        }
        Write-Host "Cloning https://github.com/$repo.git ..."
        if (Test-Path $projectDir) { Remove-Item -Recurse -Force $projectDir }
        New-Item -ItemType Directory -Force -Path $dataDir | Out-Null
        git clone --branch $branch --depth 1 "https://github.com/$repo.git" $projectDir | Out-Host
        if ($LASTEXITCODE -ne 0) { throw 'git clone failed.' }
    }

    $exe = $python[0]
    $rest = @($python | Select-Object -Skip 1)
    & $exe @rest (Join-Path $projectDir 'install.py') @args | Out-Host
    $LASTEXITCODE
} @args

if ($PSCommandPath) {
    exit $aiStatusExitCode
} elseif ($aiStatusExitCode -ne 0) {
    Write-Error "ai-cli-status-monitor installer failed (exit code $aiStatusExitCode)."
}
