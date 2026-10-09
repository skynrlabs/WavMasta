# Builds the Windows installer on your own PC: dist\installer\WavMasta-Setup-x.y.z.exe
#
# Needs Python 3.11 and Inno Setup 6 (https://jrsoftware.org/isdl.php).
# Run from the repo root in PowerShell:   .\packaging\build.ps1
# Then upload the installer to https://skynrlabs.itch.io/wavmasta

$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot)

function Step($msg) { Write-Host "`n== $msg" -ForegroundColor Cyan }
function Check($ok, $msg) { if (-not $ok) { Write-Error $msg } }

Step "Installing WavMasta and PyInstaller"
python -m pip install --upgrade pip
pip install . pyinstaller
Check ($LASTEXITCODE -eq 0) "pip install failed"
$version = python -c "import wavmasta; print(wavmasta.__version__)"

Step "Building the app ($version)"
Remove-Item -Recurse -Force dist, build -ErrorAction SilentlyContinue
pyinstaller --noconfirm packaging\wavmasta.spec
Check ($LASTEXITCODE -eq 0) "PyInstaller failed"

Step "Smoke test: master a song"
$tmp = Join-Path $env:TEMP "wavmasta-build-test"
Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue
New-Item -ItemType Directory $tmp | Out-Null
python packaging\make_test_song.py "$tmp\test-song.wav"
$p = Start-Process -FilePath "dist\WavMasta\WavMasta.exe" -Wait -PassThru `
     -ArgumentList "`"$tmp\test-song.wav`" --auto --tone country --out `"$tmp\out`""
Check ($p.ExitCode -eq 0 -and (Test-Path "$tmp\out\test-song - master.wav")) "The built app couldn't master a song"

Step "Building the installer"
$iscc = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
Check (Test-Path $iscc) "Inno Setup 6 isn't installed. Get it from https://jrsoftware.org/isdl.php"
& $iscc "/DAppVersion=$version" packaging\installer.iss
Check ($LASTEXITCODE -eq 0) "Inno Setup failed"

$exe = Get-Item "dist\installer\WavMasta-Setup-$version.exe"
Write-Host "`nDone: $($exe.FullName) ($([math]::Round($exe.Length / 1MB, 1)) MB)" -ForegroundColor Green
Write-Host "Upload it to https://skynrlabs.itch.io/wavmasta"
