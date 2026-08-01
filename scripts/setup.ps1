#!/usr/bin/env pwsh

# Configuración: lee .env y escribe .opencode/zai-key para que opencode pueda
# usar el modelo zai. No publica nada.
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent $ScriptDir
$EnvFile = Join-Path $ProjectDir ".env"
$Opendir = Join-Path $ProjectDir ".opencode"
$KeyFile = Join-Path $Opendir "zai-key"

if (-not (Test-Path -LiteralPath $EnvFile)) {
    Write-Error "Archivo .env no encontrado en $EnvFile"
    Write-Host ""
    Write-Host "  Para empezar, copia el archivo de ejemplo:"
    Write-Host "    Copy-Item -Path '$ProjectDir\.env.example' -Destination '$EnvFile'"
    Write-Host "  Luego edita $EnvFile y configura tu ZAI_API_KEY (gratis en https://z.ai)."
    exit 1
}

# Extraer ZAI_API_KEY de .env y escribirla en .opencode/zai-key (que opencode
# lee vía {file:.opencode/zai-key}). El archivo está gitignoreado.
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
        if ($key -eq "ZAI_API_KEY" -and $value) {
            $apiKey = $value
        }
    }
}

if (-not $apiKey) {
    Write-Error "ZAI_API_KEY no encontrada en $EnvFile"
    exit 1
}

if (-not (Test-Path -LiteralPath $Opendir)) {
    New-Item -ItemType Directory -Path $Opendir | Out-Null
}
Set-Content -LiteralPath $KeyFile -Value $apiKey -NoNewline

Write-Host "Listo: key escrita en $KeyFile"
