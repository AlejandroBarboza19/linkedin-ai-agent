#!/usr/bin/env pwsh
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$UserArgs
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectDir = Split-Path -Parent $ScriptDir

# Preparar la key desde .env (no publica nada).
& "$ScriptDir/setup.ps1"
if (-not $?) {
    exit 1
}

# Ejecutar opencode desde el directorio del proyecto, o el repo se percibe
# como "directorio externo" y opencode bloquea el acceso en modo no interactivo.
Set-Location -LiteralPath $ProjectDir

# Sin instrucción, publicar "Hola mundo" por defecto (demo en un solo comando).
$DEFAULT_PROMPT = "Publica un post 'Hola mundo'"
if ($UserArgs.Count -eq 0) {
    $UserArgs = @($DEFAULT_PROMPT)
}

& opencode run --agent linkedin-agent @UserArgs
if (-not $?) {
    exit $LASTEXITCODE
}
