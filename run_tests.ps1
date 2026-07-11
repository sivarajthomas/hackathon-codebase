<#
.SYNOPSIS
    Runs every MCP server's test suite in an isolated pytest process.

.DESCRIPTION
    Each MCP server is independently deployable and uses local top-level
    packages (services, models, repository, ...). Those package names collide
    if all suites are collected into a single pytest process, so this script
    invokes pytest once per server, from within that server's directory.

    Exits with a non-zero code if any server's suite fails.

.EXAMPLE
    ./run_tests.ps1
#>

[CmdletBinding()]
param(
    [string[]]$Servers = @(
        'invoice-mcp'
    )
)

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$failed = @()

foreach ($server in $Servers) {
    $serverPath = Join-Path $root $server
    if (-not (Test-Path $serverPath)) {
        Write-Warning "Skipping missing server directory: $server"
        continue
    }

    Write-Host "`n=== Running tests: $server ===" -ForegroundColor Cyan
    Push-Location $serverPath
    try {
        python -m pytest tests
        if ($LASTEXITCODE -ne 0) {
            $failed += $server
        }
    }
    finally {
        Pop-Location
    }
}

Write-Host ""
if ($failed.Count -gt 0) {
    Write-Host "FAILED: $($failed -join ', ')" -ForegroundColor Red
    exit 1
}

Write-Host "All server test suites passed." -ForegroundColor Green
exit 0
