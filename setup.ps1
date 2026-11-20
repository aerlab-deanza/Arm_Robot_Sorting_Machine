<#
Set up the Python environment for the vision code (Windows, PowerShell).

Run from the project folder:
    powershell -ExecutionPolicy Bypass -File .\setup.ps1

Options:
    -SkipTests    do not run the test suite at the end (saves about 30 seconds)

What it does:
    1. Finds Python 3.10 or newer.
    2. Makes a private environment in the .venv folder.
    3. Installs the packages in requirements.txt (and pytest).
    4. Checks that the packages load, runs the tests, and looks for cameras.
It is safe to run again. It never changes anything outside this folder.
#>
param([switch]$SkipTests)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Step($text) { Write-Host ""; Write-Host "==> $text" -ForegroundColor Cyan }
function Fail($text) { Write-Host "ERROR: $text" -ForegroundColor Red; exit 1 }

# 1. Find Python 3.10 or newer ("py" is the Windows launcher, "python" is the fallback).
Step "Looking for Python 3.10 or newer"
$python = $null
foreach ($candidate in @(@("py", "-3"), @("python"))) {
    if (-not (Get-Command $candidate[0] -ErrorAction SilentlyContinue)) { continue }
    $extra = @($candidate | Select-Object -Skip 1)
    $version = & $candidate[0] @extra -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>$null
    if ($LASTEXITCODE -ne 0 -or -not $version) { continue }
    $major, $minor = $version.Split(".") | ForEach-Object { [int]$_ }
    if ($major -eq 3 -and $minor -ge 10) { $python = $candidate; Write-Host "Found Python $version"; break }
}
if (-not $python) {
    Fail ("Python 3.10 or newer was not found.`n" +
          "Install it with:  winget install Python.Python.3.13`n" +
          "Then close this window, open a new PowerShell, and run this script again.")
}
$pythonExe = $python[0]
$pythonArgs = @($python | Select-Object -Skip 1)

# 2. Make the .venv folder.
Step "Making the .venv environment"
if (Test-Path ".venv\Scripts\python.exe") {
    Write-Host ".venv already exists, reusing it"
} else {
    & $pythonExe @pythonArgs -m venv .venv
    if ($LASTEXITCODE -ne 0) { Fail "Could not make .venv" }
}
$venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"

# 3. Install the packages.
Step "Installing packages (needs internet, about 1 minute)"
& $venvPython -m pip install --upgrade pip --quiet
& $venvPython -m pip install -r requirements.txt pytest
if ($LASTEXITCODE -ne 0) { Fail "pip could not install the packages. Check your internet and try again." }

# 4. Check the packages load.
Step "Checking the packages"
& $venvPython -c "import cv2, numpy; print('OpenCV', cv2.__version__, '| NumPy', numpy.__version__)"
if ($LASTEXITCODE -ne 0) { Fail "OpenCV or NumPy did not load" }

if (-not $SkipTests) {
    Step "Running the tests (about 30 seconds)"
    & $venvPython -m pytest tests -q
    if ($LASTEXITCODE -ne 0) { Fail "Some tests failed. Copy the text above and ask the team." }
}

Step "Looking for cameras (not an error if none is found)"
& $venvPython -c @"
import cv2
found = []
for index in range(3):
    cap = cv2.VideoCapture(index)
    if cap.isOpened():
        found.append(index)
    cap.release()
print('Camera index found:', found if found else 'none (plug in a USB camera, or use the laptop camera)')
"@

Write-Host ""
Write-Host "Setup done." -ForegroundColor Green
Write-Host "Every new PowerShell window, turn the environment on first:"
Write-Host "    .\.venv\Scripts\Activate.ps1"
Write-Host "Then run the vision code:"
Write-Host "    python vision/tray_object_pipeline.py --camera-index 0"
