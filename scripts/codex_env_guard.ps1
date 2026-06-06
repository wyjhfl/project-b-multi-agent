Param(
  [string]$Command = "",
  [string[]]$Arguments = @(),
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$PassthruArguments = @(),
  [switch]$CheckOnly
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$envRoot = Join-Path $repoRoot ".codex-env"
$xdgRoot = Join-Path $repoRoot ".git-xdg"

function Initialize-CodexEnvironment {
  [Console]::InputEncoding = [System.Text.UTF8Encoding]::new($false)
  [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
  $OutputEncoding = [System.Text.UTF8Encoding]::new($false)
  chcp 65001 | Out-Null

  New-Item -ItemType Directory -Force -Path $envRoot | Out-Null
  New-Item -ItemType Directory -Force -Path (Join-Path $xdgRoot "git") | Out-Null
  $gitIgnore = Join-Path $xdgRoot "git\ignore"
  if (-not (Test-Path -LiteralPath $gitIgnore)) {
    New-Item -ItemType File -Force -Path $gitIgnore | Out-Null
  }

  $env:XDG_CONFIG_HOME = $xdgRoot
  $env:PYTHONUTF8 = "1"
  $env:PYTHONIOENCODING = "utf-8"
}

function Resolve-PythonExecutable {
  $currentPython = Get-Command "python.exe" -ErrorAction SilentlyContinue
  if ($currentPython -and $currentPython.Source -notlike "*WindowsApps*") {
    return @($currentPython.Source)
  }

  $knownPython = Get-ChildItem -LiteralPath "D:\" -Directory -ErrorAction SilentlyContinue |
    Where-Object { $_.Name -like "codex*" } |
    ForEach-Object { Join-Path $_.FullName "tools\Python312\python.exe" } |
    Where-Object { Test-Path -LiteralPath $_ } |
    Select-Object -First 1
  if ($knownPython) {
    return @($knownPython)
  }

  $pyLauncher = Get-Command "py.exe" -ErrorAction SilentlyContinue
  if ($pyLauncher) {
    return @($pyLauncher.Source, "-3")
  }

  throw "Python runtime not found. Expected bundled Codex runtime under D:\codex*\tools\Python312\python.exe, py -3, or a non-WindowsApps python.exe on PATH."
}

function Invoke-ResolvedPython {
  param([Parameter(Mandatory = $true)][string[]]$PythonArguments)

  [string[]]$pythonCommand = @(Resolve-PythonExecutable)
  if ($pythonCommand.Count -gt 1) {
    & $pythonCommand[0] $pythonCommand[1..($pythonCommand.Count - 1)] $PythonArguments
  } else {
    & $pythonCommand[0] $PythonArguments
  }
  exit $LASTEXITCODE
}

Initialize-CodexEnvironment

if ($CheckOnly) {
  [string[]]$pythonCommand = @(Resolve-PythonExecutable)
  Write-Output "repo_root=$repoRoot"
  Write-Output "code_page=$(chcp)"
  Write-Output "input_encoding=$([Console]::InputEncoding.EncodingName)"
  Write-Output "output_encoding=$([Console]::OutputEncoding.EncodingName)"
  Write-Output "xdg_config_home=$env:XDG_CONFIG_HOME"
  Write-Output "python=$($pythonCommand[0])"
  if ($pythonCommand.Count -gt 1) {
    & $pythonCommand[0] $pythonCommand[1..($pythonCommand.Count - 1)] --version 2>$null
  } else {
    & $pythonCommand[0] --version 2>$null
  }
  exit 0
}

if ([string]::IsNullOrWhiteSpace($Command)) {
  throw "Command is required unless -CheckOnly is used."
}

$commandArguments = @()
if ($Arguments) {
  $commandArguments += $Arguments
}
if ($PassthruArguments) {
  $commandArguments += $PassthruArguments
}

switch ($Command) {
  "python" {
    Invoke-ResolvedPython -PythonArguments $commandArguments
  }
  "git" {
    & git @commandArguments
    exit $LASTEXITCODE
  }
  "npm" {
    & npm.cmd @commandArguments
    exit $LASTEXITCODE
  }
  default {
    & $Command @commandArguments
    exit $LASTEXITCODE
  }
}
