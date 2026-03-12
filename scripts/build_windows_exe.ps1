param(
    [string]$Python = "python",
    [string]$ArtifactRoot = "artifacts/windows-app",
    [switch]$Console,
    [switch]$CopyDotEnvLocal
)

$ErrorActionPreference = "Stop"
$KnownBenignBuildWarningPatterns = @(
    'WARNING:\s+Library UIAutomationClient_VC140_X64\.dll required via ctypes not found',
    'WARNING:\s+Library UIAutomationClient_VC140_X86\.dll required via ctypes not found'
)

function Normalize-WindowsPath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    if ($Path.StartsWith("\\?\UNC\")) {
        return "\" + $Path.Substring(7)
    }
    if ($Path.StartsWith("\\?\")) {
        return $Path.Substring(4)
    }
    return $Path
}

function Test-IsKnownBenignBuildWarning {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Line
    )

    foreach ($pattern in $KnownBenignBuildWarningPatterns) {
        if ($Line -match $pattern) {
            return $true
        }
    }
    return $false
}

function Invoke-BuildCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string]$StepName,
        [Parameter(Mandatory = $true)]
        [string]$Python,
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    $stdoutPath = [System.IO.Path]::GetTempFileName()
    $stderrPath = [System.IO.Path]::GetTempFileName()
    try {
        $process = Start-Process `
            -FilePath $Python `
            -ArgumentList $Arguments `
            -NoNewWindow `
            -Wait `
            -PassThru `
            -RedirectStandardOutput $stdoutPath `
            -RedirectStandardError $stderrPath

        $output = @()
        if (Test-Path $stdoutPath) {
            $output += Get-Content -Path $stdoutPath
        }
        if (Test-Path $stderrPath) {
            $output += Get-Content -Path $stderrPath
        }

        if ($process.ExitCode -ne 0) {
            if ($output.Count -gt 0) {
                $output | ForEach-Object { Write-Host $_ }
            }
            throw "$StepName failed"
        }

        $warningLines = @($output | Where-Object { "$_" -match '\bWARNING\b|\bERROR\b' })
        if ($warningLines.Count -gt 0) {
            $knownBenignWarnings = @(
                $warningLines |
                Where-Object { Test-IsKnownBenignBuildWarning -Line "$_" } |
                Sort-Object -Unique
            )
            $unexpectedWarnings = @(
                $warningLines |
                Where-Object { -not (Test-IsKnownBenignBuildWarning -Line "$_") }
            )

            if ($knownBenignWarnings.Count -gt 0) {
                Write-Host "NOTE: PyInstaller reported optional uiautomation Bitmap helper DLLs missing. Current session listener build does not use Bitmap APIs; these lines do not block worker/sidebar startup."
            }
            if ($unexpectedWarnings.Count -gt 0) {
                $unexpectedWarnings | ForEach-Object { Write-Warning "$_" }
            }
        }
    }
    finally {
        Remove-Item $stdoutPath, $stderrPath -Force -ErrorAction SilentlyContinue
    }
}

function Invoke-SmokeTestCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string]$StepName,
        [Parameter(Mandatory = $true)]
        [string]$FilePath,
        [Parameter(Mandatory = $true)]
        [string[]]$Arguments,
        [string]$FailureHint = ""
    )

    $stdoutPath = [System.IO.Path]::GetTempFileName()
    $stderrPath = [System.IO.Path]::GetTempFileName()
    try {
        $process = Start-Process `
            -FilePath $FilePath `
            -ArgumentList $Arguments `
            -NoNewWindow `
            -Wait `
            -PassThru `
            -RedirectStandardOutput $stdoutPath `
            -RedirectStandardError $stderrPath

        $output = @()
        if (Test-Path $stdoutPath) {
            $output += Get-Content -Path $stdoutPath
        }
        if (Test-Path $stderrPath) {
            $output += Get-Content -Path $stderrPath
        }

        if ($process.ExitCode -ne 0) {
            if ($output.Count -gt 0) {
                $output | ForEach-Object { Write-Host $_ }
            }
            if (-not [string]::IsNullOrWhiteSpace($FailureHint)) {
                throw "$StepName failed. $FailureHint"
            }
            throw "$StepName failed"
        }
    }
    finally {
        Remove-Item $stdoutPath, $stderrPath -Force -ErrorAction SilentlyContinue
    }
}

$ScriptPath = if ($PSCommandPath) { $PSCommandPath } else { $MyInvocation.MyCommand.Path }
if (-not $ScriptPath) {
    throw "Unable to resolve script path"
}
$ScriptPath = Normalize-WindowsPath $ScriptPath
$ScriptDir = Split-Path -Parent $ScriptPath
$RepoRoot = Split-Path -Parent $ScriptDir
$BuildParentRoot = Join-Path $RepoRoot "build"
$BuildRoot = Join-Path $RepoRoot "build\pyinstaller"
$DistRoot = Join-Path $RepoRoot $ArtifactRoot
$SpecRoot = Join-Path $BuildRoot "spec"
$WorkerDistRoot = Join-Path $BuildRoot "worker-dist"
$WorkerWorkRoot = Join-Path $BuildRoot "worker-work"
$MainWorkRoot = Join-Path $BuildRoot "main-work"
$MainName = "wechat_sidebar"
$WorkerName = "group_listener_worker"
$MainSource = Join-Path $RepoRoot "listener_app\sidebar_translate_listener.py"
$WorkerSource = Join-Path $RepoRoot "listener_app\group_listener_worker.py"
$ConfigData = "{0};config" -f (Join-Path $RepoRoot "config")
$SourceConfigPath = Join-Path $RepoRoot "config\listener.json"
$SourceDotEnvPath = Join-Path $RepoRoot ".env.local"
$ConfigRequiresDeepLXEnv = $false
$DotEnvCopied = $false

if (Test-Path $SourceConfigPath) {
    try {
        $config = Get-Content -Path $SourceConfigPath -Raw | ConvertFrom-Json
        $translate = $config.translate
        $translateEnabled = $true
        if ($null -ne $translate -and $null -ne $translate.enabled) {
            $translateEnabled = [bool]$translate.enabled
        }
        $translateProvider = "deeplx"
        if ($null -ne $translate -and $null -ne $translate.provider) {
            $translateProvider = ([string]$translate.provider).Trim().ToLowerInvariant()
        }
        $deeplxUrl = ""
        if ($null -ne $translate -and $null -ne $translate.deeplx_url) {
            $deeplxUrl = [string]$translate.deeplx_url
        }
        if (
            $translateEnabled -and
            $translateProvider -eq "deeplx" -and
            [string]::IsNullOrWhiteSpace($deeplxUrl)
        ) {
            $ConfigRequiresDeepLXEnv = $true
        }
    }
    catch {
    }
}
else {
    throw "Source config missing: $SourceConfigPath"
}

Write-Host "Preflighting source TTS dependencies..."
Invoke-SmokeTestCommand `
    -StepName "Source TTS dependency preflight" `
    -FilePath $Python `
    -Arguments @($MainSource, "--config", $SourceConfigPath, "--check-tts-deps") `
    -FailureHint "Install runtime dependencies with 'python -m pip install -r requirements.txt', or change config\\listener.json tts.provider to windows_system if you intentionally do not want to package cloud TTS."

if (Test-Path $BuildRoot) {
    Remove-Item $BuildRoot -Recurse -Force
}
if (Test-Path $DistRoot) {
    Remove-Item $DistRoot -Recurse -Force
}

New-Item -ItemType Directory -Path $BuildRoot | Out-Null
New-Item -ItemType Directory -Path $DistRoot | Out-Null
New-Item -ItemType Directory -Path $SpecRoot | Out-Null

$workerArgs = @(
    "-m", "PyInstaller",
    "--noconfirm",
    "--clean",
    "--log-level", "WARN",
    "--onefile",
    "--console",
    "--name", $WorkerName,
    "--distpath", $WorkerDistRoot,
    "--workpath", $WorkerWorkRoot,
    "--specpath", $SpecRoot,
    "--paths", $RepoRoot,
    $WorkerSource
)

Write-Host "Building worker executable..."
Invoke-BuildCommand -StepName "PyInstaller worker build" -Python $Python -Arguments $workerArgs

$mainMode = if ($Console) { "--console" } else { "--windowed" }
$mainArgs = @(
    "-m", "PyInstaller",
    "--noconfirm",
    "--clean",
    "--log-level", "WARN",
    "--onedir",
    $mainMode,
    "--name", $MainName,
    "--distpath", $DistRoot,
    "--workpath", $MainWorkRoot,
    "--specpath", $SpecRoot,
    "--paths", $RepoRoot,
    "--collect-submodules", "websockets",
    "--collect-submodules", "tencentcloud",
    "--add-data", $ConfigData,
    $MainSource
)

Write-Host "Building sidebar executable..."
Invoke-BuildCommand -StepName "PyInstaller sidebar build" -Python $Python -Arguments $mainArgs

$MainAppRoot = Join-Path $DistRoot $MainName
$WorkerExe = Join-Path $WorkerDistRoot "$WorkerName.exe"
if (-not (Test-Path $WorkerExe)) {
    throw "Worker executable missing after build: $WorkerExe"
}

Write-Host "Smoke testing worker executable..."
Invoke-SmokeTestCommand `
    -StepName "Worker smoke test (--help)" `
    -FilePath $WorkerExe `
    -Arguments @("--help")

$MainExe = Join-Path $MainAppRoot "$MainName.exe"
Write-Host "Smoke testing sidebar TTS dependencies..."
Invoke-SmokeTestCommand `
    -StepName "Sidebar TTS dependency smoke test" `
    -FilePath $MainExe `
    -Arguments @("--check-tts-deps") `
    -FailureHint "The packaged app is missing TTS runtime modules. Reinstall runtime dependencies, rebuild, and do not distribute this artifact until the smoke test passes."

Copy-Item $WorkerExe (Join-Path $MainAppRoot "$WorkerName.exe") -Force

if ($CopyDotEnvLocal) {
    if (Test-Path $SourceDotEnvPath) {
        Copy-Item $SourceDotEnvPath (Join-Path $MainAppRoot ".env.local") -Force
        $DotEnvCopied = $true
        Write-Host "NOTE: copied .env.local into the app folder. This artifact now contains local environment secrets; do not distribute it as-is."
    }
    else {
        Write-Warning "CopyDotEnvLocal requested, but source file is missing: $SourceDotEnvPath"
    }
}

if (Test-Path $BuildRoot) {
    Remove-Item $BuildRoot -Recurse -Force
}
if (Test-Path $BuildParentRoot) {
    $remaining = @(Get-ChildItem -Force $BuildParentRoot -ErrorAction SilentlyContinue)
    if ($remaining.Count -eq 0) {
        Remove-Item $BuildParentRoot -Force -ErrorAction SilentlyContinue
    }
}

Write-Host ""
Write-Host "Build completed."
Write-Host "Main app folder: $MainAppRoot"
Write-Host "Launch: $(Join-Path $MainAppRoot "$MainName.exe")"
if ($ConfigRequiresDeepLXEnv -and -not $DotEnvCopied) {
    Write-Host "NOTE: current config relies on DEEPLX_URL. .env.local is not copied into the app folder. Put .env.local beside wechat_sidebar.exe or set config\\listener.json translate.deeplx_url before launching."
}
