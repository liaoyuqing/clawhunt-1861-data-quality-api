# Start the private PostgreSQL 16 cluster used by the demo and the integration tests.
#
#   pwsh -File scripts/start_pg.ps1
#
# The data directory lives outside the repository (../../_pgdata) so no database
# files ever end up in the delivered source tree.

param(
    [int]$Port = 55433,
    [string]$DataDir = (Join-Path $PSScriptRoot "..\..\_pgdata")
)

$ErrorActionPreference = "Stop"
$pgBin = "C:/pgsql16/bin"
if (-not (Test-Path $pgBin)) {
    throw "PostgreSQL 16 binaries not found at $pgBin"
}

if (-not (Test-Path $DataDir)) {
    New-Item -ItemType Directory -Force -Path $DataDir | Out-Null
    & "$pgBin/initdb.exe" -D $DataDir -U postgres -E UTF8 --locale=C --auth=trust
    if ($LASTEXITCODE -ne 0) { throw "initdb failed" }
}

Start-Process -FilePath "$pgBin/postgres.exe" `
    -ArgumentList @("-D", $DataDir, "-p", $Port, "-c", "listen_addresses=127.0.0.1") `
    -RedirectStandardOutput "$DataDir/out.log" -RedirectStandardError "$DataDir/err.log" `
    -WindowStyle Hidden
Start-Sleep -Seconds 4
& "$pgBin/psql.exe" -h 127.0.0.1 -p $Port -U postgres -d postgres -tAc "select 1;"
if ($LASTEXITCODE -ne 0) { throw "postgres did not accept connections on port $Port" }
Write-Output "POSTGRES_READY port=$Port data=$DataDir"