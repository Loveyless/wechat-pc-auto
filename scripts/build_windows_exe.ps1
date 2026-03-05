param(
    [string]$PythonExe = "python",
    [switch]$OneFile,
    [switch]$Console
)

$ErrorActionPreference = "Stop"

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $root

$distPath = Join-Path $root "artifacts\\dist"
$workPath = Join-Path $root "artifacts\\build"
$specPath = Join-Path $root "artifacts\\spec"

New-Item -ItemType Directory -Force -Path $distPath | Out-Null
New-Item -ItemType Directory -Force -Path $workPath | Out-Null
New-Item -ItemType Directory -Force -Path $specPath | Out-Null

$hasPyInstaller = $false
try {
    & $PythonExe -m PyInstaller --version *> $null
    if ($LASTEXITCODE -eq 0) {
        $hasPyInstaller = $true
    }
} catch {
    $hasPyInstaller = $false
}

if (-not $hasPyInstaller) {
    & $PythonExe -m pip install pyinstaller
}

$modeFlag = if ($OneFile) { "--onefile" } else { "--onedir" }
$windowFlag = if ($Console) { "--console" } else { "--windowed" }
$configSource = Join-Path $root "config"

$args = @(
    "-m", "PyInstaller",
    "--noconfirm",
    "--clean",
    $modeFlag,
    $windowFlag,
    "--name", "wechat-listener",
    "--distpath", $distPath,
    "--workpath", $workPath,
    "--specpath", $specPath,
    "--add-data", "$configSource;config",
    "--hidden-import", "examples.group_listener_worker",
    "examples/sidebar_translate_listener.py"
)

try {
    $uiaBin = (& $PythonExe -c "import os,uiautomation;print(os.path.join(os.path.dirname(uiautomation.__file__),'bin'))").Trim()
    $uiaX64 = Join-Path $uiaBin "UIAutomationClient_VC140_X64.dll"
    $uiaX86 = Join-Path $uiaBin "UIAutomationClient_VC140_X86.dll"
    if (Test-Path $uiaX64) {
        $args += @("--add-binary", "$uiaX64;.")
    }
    if (Test-Path $uiaX86) {
        $args += @("--add-binary", "$uiaX86;.")
    }
} catch {
    Write-Warning "Auto-collect uiautomation dll failed: $($_.Exception.Message)"
}

& $PythonExe @args
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller build failed."
}

$copyTargets = @()
if ($OneFile) {
    $copyTargets += $distPath
} else {
    $copyTargets += (Join-Path $distPath "wechat-listener")
}

foreach ($targetRoot in $copyTargets) {
    $targetConfig = Join-Path $targetRoot "config"
    New-Item -ItemType Directory -Force -Path $targetConfig | Out-Null
    Copy-Item -Path (Join-Path $configSource "listener.json") -Destination (Join-Path $targetConfig "listener.json") -Force
    $listenerDoc = Join-Path $configSource "listener.md"
    if (Test-Path $listenerDoc) {
        Copy-Item -Path $listenerDoc -Destination (Join-Path $targetConfig "listener.md") -Force
    }
}

Write-Output "Build done."
if ($OneFile) {
    Write-Output "EXE: $distPath\\wechat-listener.exe"
    Write-Output "Config: $distPath\\config\\listener.json"
} else {
    Write-Output "AppDir: $distPath\\wechat-listener"
    Write-Output "Config: $distPath\\wechat-listener\\config\\listener.json"
}
