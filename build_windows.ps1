$ErrorActionPreference = "Stop"

Set-Location $PSScriptRoot

Write-Host ""
Write-Host "Kaokey Windows build"
Write-Host "===================="

if (Test-Path ".\.venv\Scripts\python.exe") {
    $Python = ".\.venv\Scripts\python.exe"
}
else {
    $Python = "python"
}

Write-Host "Python:"
& $Python --version

Write-Host ""
Write-Host "PyInstaller:"
& $Python -m PyInstaller --version

if ($LASTEXITCODE -ne 0) {
    throw @"
PyInstaller is not available in this Python environment.

Install the build dependencies first:
    python -m pip install -r requirements-dev.txt
"@
}

$RequiredFiles = @(
    ".\main.py",
    ".\Kaokey.spec",
    ".\version_info.txt",
    ".\data\kaomoji.json",
    ".\data\constructor_symbols.json",
    ".\resources\icons\kaokey.ico"
)

foreach ($File in $RequiredFiles) {
    if (-not (Test-Path $File)) {
        throw "Required build file is missing: $File"
    }
}

Write-Host ""
Write-Host "Validating default kaomoji seed..."

$SeedCheck = @'
import json
from pathlib import Path

path = Path("data/kaomoji.json")
data = json.loads(path.read_text(encoding="utf-8"))

assert data.get("format_version") == 1
assert data.get("active_list") == "Default"

lists = data.get("lists")
assert isinstance(lists, list)
assert len(lists) >= 1

default = next(
    (
        item
        for item in lists
        if item.get("name") == "Default"
    ),
    None,
)

assert default is not None

kaomoji = default.get("kaomoji")
assert isinstance(kaomoji, list)
assert len(kaomoji) >= 300

print(
    f"Default seed OK: {len(kaomoji)} kaomoji"
)
'@

$SeedCheck | & $Python -

if ($LASTEXITCODE -ne 0) {
    throw "The default kaomoji seed failed validation."
}

Write-Host ""
Write-Host "Building one-file Kaokey.exe..."
& $Python -m PyInstaller `
    --clean `
    --noconfirm `
    ".\Kaokey.spec"

if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller build failed."
}

$ExePath = ".\dist\Kaokey.exe"

if (-not (Test-Path $ExePath)) {
    throw "Build finished without dist\Kaokey.exe."
}

$Exe = Get-Item $ExePath

$SizeMb = [Math]::Round(
    $Exe.Length / 1MB,
    2
)

Write-Host ""
Write-Host "Build complete."
Write-Host ("Path: " + $Exe.FullName)
Write-Host ("Size: {0} MB" -f $SizeMb)
Write-Host ""
Write-Host "Next:"
Write-Host "    .\dist\Kaokey.exe"
Write-Host ""
Write-Host "Then follow PACKAGING.md smoke tests."
