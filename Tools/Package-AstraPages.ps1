param(
    [string]$EngineRoot,
    [string]$EmsdkRoot = $env:WASM_EMSDK_ROOT,
    [switch]$ReuseCook
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path $PSScriptRoot -Parent
$project = Join-Path $projectRoot "gameAstraForest.uproject"
if (-not $EngineRoot) {
    $version = (Get-Content -Raw -LiteralPath $project | ConvertFrom-Json).EngineAssociation
    $EngineRoot = Join-Path $env:ProgramFiles "Epic Games/UE_$version"
}
$batchFiles = Join-Path $EngineRoot "Engine/Build/BatchFiles"
$release = Join-Path $projectRoot "Saved/PagesRelease"
$previousSdk = $env:UE_SDKS_ROOT
$previousEmsdk = $env:WASM_EMSDK_ROOT
$previousCores = $env:BINARYEN_CORES
try {
    $localSdk = Join-Path $env:LOCALAPPDATA "Codex/UnrealToolchains/WinSDK26100"
    if (-not $previousSdk -and (Test-Path -LiteralPath $localSdk)) { $env:UE_SDKS_ROOT = $localSdk }
    if ($EmsdkRoot) { $env:WASM_EMSDK_ROOT = (Resolve-Path -LiteralPath $EmsdkRoot).Path }
    if (-not $previousCores) { $env:BINARYEN_CORES = "7" }
    if (-not $ReuseCook) {
        & (Join-Path $PSScriptRoot "Build-Astra.ps1") -Target Editor -EngineRoot $EngineRoot
    }
    & (Join-Path $batchFiles "Build.bat") gameAstraForest Wasm Shipping "-Project=$project" -WaitMutex -NoUBA -MaxParallelActions=4
    if ($LASTEXITCODE -ne 0) { throw "Unreal Wasm compilation failed ($LASTEXITCODE)." }

    $cook = if ($ReuseCook) { "-skipcook" } else { "-cook" }
    & (Join-Path $batchFiles "RunUAT.bat") BuildCookRun "-project=$project" -platform=Wasm -clientconfig=Shipping `
        -skipbuild $cook -stage -pak -iostore -compressed -package -archive "-stagingdirectory=$release/Staged" `
        "-archivedirectory=$release/Archive" -map=/Game/AstraTemple/Maps/L_CanopyDeathmatch -cookcultures=en `
        -nop4 -nocompileeditor -nodebuginfo -unattended -utf8output -WasmNoBrotli "-AdditionalCookerOptions=-NoAlwaysCookMaps"
    if ($LASTEXITCODE -ne 0) { throw "Unreal Wasm packaging failed ($LASTEXITCODE)." }

    $stage = Join-Path $release "Archive/Wasm"
    $checkStage = Join-Path $EngineRoot "Engine/Platforms/Wasm/Build/Tools/deploy/check_stage.py"
    & python $checkStage $stage
    if ($LASTEXITCODE -ne 0) { throw "Unreal release validation failed ($LASTEXITCODE)." }
    & python (Join-Path $PSScriptRoot "pages/prepare.py") --stage $stage --output "$projectRoot/WebRelease"
    if ($LASTEXITCODE -ne 0) { throw "Static site preparation failed ($LASTEXITCODE)." }
} finally {
    $env:UE_SDKS_ROOT = $previousSdk
    $env:WASM_EMSDK_ROOT = $previousEmsdk
    $env:BINARYEN_CORES = $previousCores
}
