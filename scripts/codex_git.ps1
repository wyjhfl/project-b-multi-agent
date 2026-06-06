Param(
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$Arguments = @()
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

[Console]::InputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$script:OutputEncoding = [System.Text.UTF8Encoding]::new($false)
chcp 65001 | Out-Null

$xdgRoot = Join-Path $repoRoot ".git-xdg"
New-Item -ItemType Directory -Force -Path (Join-Path $xdgRoot "git") | Out-Null
$gitIgnore = Join-Path $xdgRoot "git\ignore"
if (-not (Test-Path -LiteralPath $gitIgnore)) {
  New-Item -ItemType File -Force -Path $gitIgnore | Out-Null
}

$env:XDG_CONFIG_HOME = $xdgRoot

& git @Arguments
exit $LASTEXITCODE
