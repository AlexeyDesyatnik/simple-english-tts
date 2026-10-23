<#
  Developer-only build of the program's runtime (ADR-0001). Nothing in tools\ ships.

  Modes:
    dev      runtime\ and models\ inside the repository, plus pytest
    release  (not implemented yet) program folder and zip

  Run: tools\build.bat dev   (or powershell -ExecutionPolicy Bypass -File tools\build.ps1 -Mode dev)
  Needs internet. Downloads are cached in .cache\ and already finished steps are skipped,
  so the script can simply be run again after a failure.

  Keep this file ASCII-only: Windows PowerShell 5.1 misreads UTF-8 without a BOM.
#>
param(
    [Parameter(Mandatory = $true)][ValidateSet('dev', 'release')][string]$Mode
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'   # otherwise Invoke-WebRequest in PS 5.1 is very slow
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

if ($Mode -eq 'release') { throw 'Release mode is not implemented yet.' }

$Tools   = $PSScriptRoot
$Root    = Split-Path $Tools
$Runtime = Join-Path $Root 'runtime'
$Models  = Join-Path $Root 'models'
$Cache   = Join-Path $Root '.cache'
$Py      = Join-Path $Runtime 'python.exe'

$PyVer = '3.12.10'

$SpacyModel  = 'en_core_web_sm'
$SpacyVer    = '3.8.0'
$SpacySha256 = '1932429db727d4bff3deed6b34cfc05df17794f4a52eeb26cf8928f7c1a0fb85'

# onnx-community/Kokoro-82M-v1.0-ONNX, pinned to a commit; sha256 from the Hugging Face LFS metadata.
$KokoroRepo  = 'https://huggingface.co/onnx-community/Kokoro-82M-v1.0-ONNX/resolve/1939ad2a8e416c0acfeecc08a694d14ef25f2231'
$KokoroModel = @{ Path = 'onnx/model_quantized.onnx'; Sha256 = 'fbae9257e1e05ffc727e951ef9b9c98418e6d79f1c9b6b13bd59f5c9028a1478' }
$KokoroVoices = [ordered]@{
    bf_alice    = '08afa6ba24da61ea5e8efa139e5aadc938d83f0a6da5a900adaf763ac1da5573'
    bf_emma     = '669fe0647f9dd04fcab92f1439a40eeb4c8b4ab1f82e4996fe3d918ce4a63b73'
    bf_isabella = '3754352c4aaa46d17f27654ab7518d65b62ad6163a0f55a5f4330c2da2c4e94f'
    bf_lily     = '5e0ee32ebe64a467124976b14e69590746f1c4ce41a12b587a50c862edfea335'
    bm_daniel   = '6b3194bbceffb746733cbc22c8f593dd44e401a71d53895a2dca891bc595a1e8'
    bm_fable    = 'f889083196807b4adb15e9204252165f503b8d33d3982e681c52443c49d798f1'
    bm_george   = 'c4b235a4c1f2cd3b939fed08b899ce9385638b763f7b73a59616c4fc9bd6c9bc'
    bm_lewis    = 'b8f671cef828c30e66fdf0b0756a76bba58f6bb3398cbbf27058642acbcedb97'
}

$HasCurl = [bool](Get-Command curl.exe -ErrorAction SilentlyContinue)

function Step($text) { Write-Host ""; Write-Host "=== $text" -ForegroundColor Cyan }

function Get-File([string]$Url, [string]$Dest) {
    if (Test-Path $Dest) { Write-Host "  cached: $(Split-Path $Dest -Leaf)"; return }
    New-Item -ItemType Directory -Force -Path (Split-Path $Dest) | Out-Null
    $tmp = "$Dest.part"
    Write-Host "  downloading $Url"
    try {
        if ($HasCurl) {
            & curl.exe -sS -L --fail --retry 3 --retry-delay 3 -C - -o $tmp $Url
            if ($LASTEXITCODE -ne 0) { throw "curl exited with code $LASTEXITCODE" }
        } else {
            Invoke-WebRequest -Uri $Url -OutFile $tmp -UseBasicParsing
        }
    } catch {
        if (Test-Path $tmp) { Remove-Item -Force $tmp }
        throw "Could not download $(Split-Path $Dest -Leaf): $_"
    }
    Move-Item -Force $tmp $Dest
}

# Get-FileHash and Expand-Archive live in script modules that do not load when PSModulePath
# is spoiled (e.g. started from a pwsh 7 terminal), so hashing and unzipping go through .NET.
function Get-Sha256([string]$Path) {
    $sha = [System.Security.Cryptography.SHA256]::Create()
    $stream = [System.IO.File]::OpenRead($Path)
    try { $bytes = $sha.ComputeHash($stream) } finally { $stream.Dispose(); $sha.Dispose() }
    return ([System.BitConverter]::ToString($bytes) -replace '-', '').ToLower()
}

function Assert-Sha256([string]$Path, [string]$Expected) {
    $hash = Get-Sha256 $Path
    if ($hash -ne $Expected) {
        Remove-Item -Force $Path
        throw "Checksum mismatch for $(Split-Path $Path -Leaf) (got $hash). The file was removed; run the script again."
    }
}

function Expand-Zip([string]$Zip, [string]$Dest) {
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    New-Item -ItemType Directory -Force -Path $Dest | Out-Null
    $archive = [System.IO.Compression.ZipFile]::OpenRead($Zip)
    try {
        foreach ($entry in $archive.Entries) {
            $target = Join-Path $Dest $entry.FullName
            if ($entry.FullName.EndsWith('/')) { New-Item -ItemType Directory -Force -Path $target | Out-Null; continue }
            New-Item -ItemType Directory -Force -Path (Split-Path $target) | Out-Null
            [System.IO.Compression.ZipFileExtensions]::ExtractToFile($entry, $target, $true)
        }
    } finally { $archive.Dispose() }
}

function Invoke-Py {
    & $Py @args
    if ($LASTEXITCODE -ne 0) { throw "python $($args -join ' ') exited with code $LASTEXITCODE" }
}

# ------------------------------------------------------------------ Python
Step "Python $PyVer (embeddable)"
if (-not (Test-Path $Py)) {
    $zip = Join-Path $Cache "python-$PyVer-embed-amd64.zip"
    Get-File "https://www.python.org/ftp/python/$PyVer/python-$PyVer-embed-amd64.zip" $zip
    Expand-Zip $zip $Runtime
}
# Enable site (pip, site-packages) and put the program folder (the parent of runtime\) on sys.path:
# embeddable Python adds neither the script folder nor the current folder.
$pth = (Get-ChildItem $Runtime -Filter 'python*._pth' | Select-Object -First 1).FullName
$lines = @(Get-Content $pth | Where-Object { $_ -ne '#import site' -and $_ -ne 'import site' -and $_ -ne '..' })
$lines += '..'
$lines += 'import site'
Set-Content -Encoding Ascii -Path $pth -Value $lines
Write-Host "  OK: $Py"

# ------------------------------------------------------------------ packages
Step "pip and packages"
# In PS 5.1 redirected stderr turns into an exception when ErrorActionPreference is Stop
$ErrorActionPreference = 'Continue'
& $Py -m pip --version 2>&1 | Out-Null
$hasPip = ($LASTEXITCODE -eq 0)
$ErrorActionPreference = 'Stop'
if (-not $hasPip) {
    $getpip = Join-Path $Cache 'get-pip.py'
    Get-File 'https://bootstrap.pypa.io/get-pip.py' $getpip
    Invoke-Py $getpip --no-warn-script-location
}
$pipArgs = @('-m', 'pip', 'install', '--no-warn-script-location', '--disable-pip-version-check', '--only-binary=:all:')
$requirements = @('-r', (Join-Path $Tools 'requirements.txt'))
if ($Mode -eq 'dev') { $requirements += @('-r', (Join-Path $Tools 'requirements-dev.txt')) }
Invoke-Py @pipArgs -c (Join-Path $Tools 'constraints.txt') @requirements
Invoke-Py @pipArgs --no-deps -r (Join-Path $Tools 'requirements-nodeps.txt')

# ------------------------------------------------------------------ spaCy model
# misaki needs it for part-of-speech tagging (lives: verb or noun). It is not on PyPI.
Step "spaCy model ($SpacyModel $SpacyVer)"
$ErrorActionPreference = 'Continue'
$installed = (& $Py -c "import importlib.metadata as m; print(m.version('$SpacyModel'))" 2>$null)
$ErrorActionPreference = 'Stop'
if ($installed -eq $SpacyVer) {
    Write-Host "  already installed"
} else {
    $whlName = "$SpacyModel-$SpacyVer-py3-none-any.whl"
    $whl = Join-Path $Cache $whlName
    Get-File "https://github.com/explosion/spacy-models/releases/download/$SpacyModel-$SpacyVer/$whlName" $whl
    Assert-Sha256 $whl $SpacySha256
    Invoke-Py @pipArgs --no-deps --force-reinstall $whl
}

# ------------------------------------------------------------------ Visual C++ libraries
# onnxruntime and espeak-ng need msvcp140*.dll, which school laptops may not have.
Step "Visual C++ libraries"
$sys32 = if ([Environment]::Is64BitProcess) { "$env:windir\System32" } else { "$env:windir\Sysnative" }
foreach ($dll in 'msvcp140.dll', 'msvcp140_1.dll', 'vcruntime140.dll', 'vcruntime140_1.dll') {
    $src = Join-Path $sys32 $dll
    if (Test-Path (Join-Path $Runtime $dll)) { Write-Host "  present: $dll" }
    elseif (Test-Path $src) { Copy-Item $src $Runtime; Write-Host "  copied $dll" }
    else {
        throw "$dll is missing on this computer. Install the Visual C++ Redistributable (https://aka.ms/vs/17/release/vc_redist.x64.exe) and run the script again."
    }
}

# ------------------------------------------------------------------ Kokoro
Step "Kokoro model and British voices"
$k = Join-Path $Models 'kokoro'
$model = Join-Path $k 'kokoro-int8.onnx'
if (-not (Test-Path $model)) {
    $download = Join-Path $Cache 'kokoro-int8.onnx'
    Get-File "$KokoroRepo/$($KokoroModel.Path)" $download
    Assert-Sha256 $download $KokoroModel.Sha256
    New-Item -ItemType Directory -Force -Path $k | Out-Null
    Copy-Item -Force $download $model
}
$voiceDir = Join-Path $Cache 'kokoro-voices'
foreach ($v in $KokoroVoices.Keys) {
    $bin = Join-Path $voiceDir "$v.bin"
    if (-not (Test-Path $bin)) {
        Get-File "$KokoroRepo/voices/$v.bin" $bin
        Assert-Sha256 $bin $KokoroVoices[$v]
    }
}
Invoke-Py (Join-Path $Tools 'pack_kokoro_voices.py') $voiceDir (Join-Path $k 'voices.npz')

# ------------------------------------------------------------------ check
Step "Check"
$env:PYTHONUTF8 = '1'
Invoke-Py -c "import kokoro_onnx, misaki.en, spacy, ozvuchka; assert spacy.util.is_package('$SpacyModel'); print('  imports OK')"

Write-Host ""
Write-Host "Done. Run the tests with: runtime\python.exe -m pytest" -ForegroundColor Green
