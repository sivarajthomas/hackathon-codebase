<#
.SYNOPSIS
    Load a .env profile file into the CURRENT PowerShell session.

.DESCRIPTION
    The BigQuery MCP server runs Google's toolbox binary, which reads its
    configuration from environment variables (it does not read .env files).
    Dot-source this script to export a profile's variables into the session,
    then launch the toolbox with the same config the Python servers use.

.EXAMPLE
    # Note the leading dot -- it makes the variables persist in your session.
    . .\scripts\Load-EnvFile.ps1 -Path .env
    .\bigquery-mcp\toolbox.exe --config .\bigquery-mcp\tools.yaml --stdio

.PARAMETER Path
    Path to the .env profile file. Defaults to '.env' at the repository root.
#>
param(
    [string]$Path = ".env"
)

if (-not (Test-Path $Path)) {
    throw "Env file not found: $Path"
}

Get-Content $Path | ForEach-Object {
    $line = $_.Trim()
    if ($line -eq "" -or $line.StartsWith("#") -or ($line -notmatch "=")) { return }
    $key, $value = $line -split "=", 2
    $key = $key.Trim()
    $value = $value.Trim().Trim('"').Trim("'")
    if ($key) {
        Set-Item -Path "Env:$key" -Value $value
    }
}

Write-Host "Loaded environment from '$Path'." -ForegroundColor Green
