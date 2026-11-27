# Clean-room verification for order 1861.
#
# Extracts the committed tree (git archive HEAD) into clean/, creates a brand new
# virtualenv there, then runs every step of the delivery checklist and stores the real
# output under clean/docs/checks/*.txt.
#
# The script is deliberately ASCII-only and derives every path from $PSScriptRoot, so
# Windows PowerShell 5.1 (which decodes .ps1 files as ANSI without a BOM) can run it.

$ErrorActionPreference = "Continue"
$Work = $PSScriptRoot
$Repo = Join-Path $Work "repo"
$Clean = Join-Path $Work "clean"
$Checks = Join-Path $Clean "docs\checks"
$Py = "C:/Users/Administrator/.venvs/hf-bgm/Scripts/python.exe"
$Tar = Join-Path $Work "clean.tar"

if (Test-Path $Clean) { cmd /c "rmdir /s /q `"$Clean`"" }
New-Item -ItemType Directory -Force -Path $Clean | Out-Null

Push-Location $Repo
git archive --format=tar HEAD -o $Tar
Write-Output "GIT_ARCHIVE_EXIT=$LASTEXITCODE"
Pop-Location

tar -xf $Tar -C $Clean
Write-Output "TAR_EXTRACT_EXIT=$LASTEXITCODE"
Remove-Item -Force $Tar -ErrorAction SilentlyContinue

New-Item -ItemType Directory -Force -Path $Checks | Out-Null

$venvPy = Join-Path $Clean ".venv\Scripts\python.exe"
& $Py -m venv (Join-Path $Clean ".venv")
Write-Output "VENV_CREATE_EXIT=$LASTEXITCODE"

$env:DQ_TEST_DATABASE_URL = "postgresql+psycopg://postgres@127.0.0.1:55433/dq1861"
$env:DQ_DATABASE_URL = "postgresql+psycopg://postgres@127.0.0.1:55433/dq1861"
$env:PIP_DISABLE_PIP_VERSION_CHECK = "1"

Push-Location $Clean

& $venvPy -m pip install --upgrade pip 2>&1 | Out-File -FilePath (Join-Path $Checks "pip-install.txt") -Encoding utf8
Write-Output "PIP_UPGRADE_EXIT=$LASTEXITCODE"

& $venvPy -m pip install -r requirements-dev.txt 2>&1 | Out-File -FilePath (Join-Path $Checks "pip-install.txt") -Encoding utf8
Write-Output "PIP_INSTALL_EXIT=$LASTEXITCODE"

& $venvPy -m pytest -v --no-header 2>&1 | Out-File -FilePath (Join-Path $Checks "pytest.txt") -Encoding utf8
Write-Output "PYTEST_EXIT=$LASTEXITCODE"

& $venvPy -m mypy 2>&1 | Out-File -FilePath (Join-Path $Checks "mypy.txt") -Encoding utf8
Write-Output "MYPY_EXIT=$LASTEXITCODE"

& $venvPy -m ruff check . 2>&1 | Out-File -FilePath (Join-Path $Checks "ruff.txt") -Encoding utf8
Write-Output "RUFF_EXIT=$LASTEXITCODE"

& $venvPy -m build --wheel --sdist 2>&1 | Out-File -FilePath (Join-Path $Checks "build.txt") -Encoding utf8
Write-Output "BUILD_EXIT=$LASTEXITCODE"

& $venvPy scripts/export_openapi.py 2>&1 | Out-File -FilePath (Join-Path $Checks "openapi-export.txt") -Encoding utf8
Write-Output "OPENAPI_EXIT=$LASTEXITCODE"

& $venvPy scripts/smoke_api.py --version v1 2> (Join-Path $Checks "smoke-run-v1.err.txt") | Out-File -FilePath (Join-Path $Checks "smoke-run-v1.txt") -Encoding utf8
Write-Output "SMOKE_V1_EXIT=$LASTEXITCODE"
& $venvPy scripts/smoke_api.py --version v2 2> (Join-Path $Checks "smoke-run-v2.err.txt") | Out-File -FilePath (Join-Path $Checks "smoke-run-v2.txt") -Encoding utf8
Write-Output "SMOKE_V2_EXIT=$LASTEXITCODE"

Pop-Location

Write-Output "--- pytest tail ---"
Get-Content (Join-Path $Checks "pytest.txt") -Tail 4
Write-Output "--- mypy tail ---"
Get-Content (Join-Path $Checks "mypy.txt") -Tail 2
Write-Output "--- ruff tail ---"
Get-Content (Join-Path $Checks "ruff.txt") -Tail 2
Write-Output "--- build tail ---"
Get-Content (Join-Path $Checks "build.txt") -Tail 2
Write-Output "--- openapi tail ---"
Get-Content (Join-Path $Checks "openapi-export.txt") -Tail 6
Write-Output "--- smoke tail ---"
Get-Content (Join-Path $Checks "smoke-run-v1.txt") -Tail 2
Write-Output "--- smoke v2 tail ---"
Get-Content (Join-Path $Checks "smoke-run-v2.txt") -Tail 2

Write-Output "CLEAN_VERIFICATION_DONE"