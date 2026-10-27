# Wraps the built app into an MSIX package for the Microsoft Store: dist\msix\<App>-x.y.z.0-x64.msix
#
# Run packaging\build.ps1 first (it builds dist\<App>), then, from the repo root in PowerShell:
#     .\packaging\build-msix.ps1
# Needs the Windows 10/11 SDK (for makeappx.exe and makepri.exe) and Python with Pillow.
#
# The Store signs MSIX packages itself, so no code-signing certificate is needed. The package identity
# must match Partner Center exactly: fill in packaging\msix\identity.json first. Until then this builds
# a TEST package (publisher CN=SkynrLabsTest) that the Store won't accept.

$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot)

function Step($msg) { Write-Host "`n== $msg" -ForegroundColor Cyan }
function Check($ok, $msg) { if (-not $ok) { Write-Error $msg } }

$app = "WavMasta"
$module = "wavmasta"
$description = "Clean up and master your songs, ready for release."

Check (Test-Path "dist\$app\$app.exe") "dist\$app\$app.exe isn't there. Run .\packaging\build.ps1 first."
$python = (Get-Command python -ErrorAction SilentlyContinue).Source
Check ($python) "Python isn't on PATH"
$version = & $python -c "import $module; print($module.__version__)"
Check ($LASTEXITCODE -eq 0 -and $version -match '^\d+\.\d+\.\d+$') "Couldn't read the version (got '$version')"
$msixVersion = "$version.0"  # the Store needs four numbers, the last one 0

Step "Package identity"
$id = Get-Content packaging\msix\identity.json -Raw | ConvertFrom-Json
$test = $id.name -like "REPLACE*" -or $id.publisher -like "REPLACE*"
if ($test) {
    $id.name = "SkynrLabs.$app.Test"
    $id.publisher = "CN=SkynrLabsTest"
    Write-Warning "packaging\msix\identity.json isn't filled in, so this is a TEST package the Store won't accept."
}
Check ($id.publisher -like "CN=*") "The publisher in identity.json should start with CN="
Write-Host "$($id.name)  ·  $($id.publisher)  ·  $msixVersion"

Step "Laying out the package"
$root = "dist\msix\root"
Remove-Item -Recurse -Force dist\msix -ErrorAction SilentlyContinue
New-Item -ItemType Directory $root | Out-Null
Copy-Item -Recurse "dist\$app" "$root\$app"
& $python -m pip install --quiet pillow
& $python packaging\msix\make_assets.py "$module\assets\icon.png" "$root\Assets"
Check ($LASTEXITCODE -eq 0) "Couldn't make the icons"
$manifest = (Get-Content packaging\msix\AppxManifest.xml -Raw).
    Replace("{NAME}", $id.name).
    Replace("{PUBLISHER}", $id.publisher).
    Replace("{PUBLISHER_DISPLAY_NAME}", $id.publisher_display_name).
    Replace("{VERSION}", $msixVersion).
    Replace("{APP}", $app).
    Replace("{DESCRIPTION}", $description)
[IO.File]::WriteAllText((Resolve-Path $root).Path + "\AppxManifest.xml", $manifest, (New-Object Text.UTF8Encoding $false))

Step "Finding the Windows SDK tools"
$sdk = Get-ChildItem "${env:ProgramFiles(x86)}\Windows Kits\10\bin\10.*\x64\makeappx.exe" -ErrorAction SilentlyContinue |
    Sort-Object FullName -Descending | Select-Object -First 1
Check ($sdk) "makeappx.exe wasn't found. Install the Windows 10/11 SDK: https://developer.microsoft.com/windows/downloads/windows-sdk/"
$makeappx = $sdk.FullName
$makepri = Join-Path $sdk.DirectoryName "makepri.exe"
Write-Host "Using $makeappx"

Step "Indexing the icons (resources.pri)"
& $makepri createconfig /cf dist\msix\priconfig.xml /dq en-US /o | Out-Null
Check ($LASTEXITCODE -eq 0) "makepri createconfig failed"
& $makepri new /pr $root /cf dist\msix\priconfig.xml /mn "$root\AppxManifest.xml" /of "$root\resources.pri" /o
Check ($LASTEXITCODE -eq 0) "makepri new failed"

Step "Packing"
$suffix = if ($test) { "-TEST" } else { "" }
$msix = "dist\msix\$app-$msixVersion-x64$suffix.msix"
& $makeappx pack /d $root /p $msix /o
Check ($LASTEXITCODE -eq 0 -and (Test-Path $msix)) "makeappx pack failed"

$file = Get-Item $msix
Write-Host "`nDone: $($file.FullName) ($([math]::Round($file.Length / 1MB, 1)) MB)" -ForegroundColor Green
if ($test) { Write-Host "TEST package: fill in packaging\msix\identity.json for one the Store accepts." -ForegroundColor Yellow }
else { Write-Host "Upload it in Partner Center: your app > Packages." }
