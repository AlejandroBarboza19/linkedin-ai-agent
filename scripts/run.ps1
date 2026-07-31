#!/usr/bin/env pwsh
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$UserArgs
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent $ScriptDir
$EnvFile = Join-Path $ProjectDir ".env"
$Opendir = Join-Path $ProjectDir ".opencode"
$KeyFile = Join-Path $Opendir "openrouter-key"

if (-not (Test-Path -LiteralPath $EnvFile)) {
    Write-Error ".env file not found at $EnvFile"
    Write-Host ""
    Write-Host "  To get started, copy the example file:"
    Write-Host "    Copy-Item -Path '$ProjectDir\.env.example' -Destination '$EnvFile'"
    Write-Host "  Then edit $EnvFile and set your OPENROUTER_API_KEY."
    exit 1
}

# Extract OPENROUTER_API_KEY from .env and write it to .opencode/openrouter-key
$apiKey = $null
Get-Content -LiteralPath $EnvFile | ForEach-Object {
    $line = $_.Trim()
    if ($line -eq "" -or $line.StartsWith("#")) {
        return
    }
    $eqIndex = $line.IndexOf("=")
    if ($eqIndex -gt 0) {
        $key = $line.Substring(0, $eqIndex).Trim()
        $value = $line.Substring($eqIndex + 1).Trim()
        if ($key -eq "OPENROUTER_API_KEY" -and $value) {
            $apiKey = $value
        }
    }
}

if (-not $apiKey) {
    Write-Error "OPENROUTER_API_KEY not found in $EnvFile"
    exit 1
}

Set-Content -LiteralPath $KeyFile -Value $apiKey -NoNewline

& opencode run --agent linkedin-agent @UserArgs
if (-not $?) {
    exit $LASTEXITCODE
}
