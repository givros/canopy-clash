param(
    [switch]$CookOnly,
    [switch]$StageOnly,
    [switch]$ReuseCook,
    [switch]$FullCook,
    [ValidateSet("Shipping", "Development")]
    [string]$Configuration = "Shipping",
    [string]$EngineRoot
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path $PSScriptRoot -Parent
$project = Join-Path $projectRoot "gameAstraForest.uproject"
$association = (Get-Content -Raw -LiteralPath $project | ConvertFrom-Json).EngineAssociation
if (-not $EngineRoot) {
    $EngineRoot = Join-Path $env:ProgramFiles "Epic Games/UE_$association"
}
$uat = Join-Path $EngineRoot "Engine/Build/BatchFiles/RunUAT.bat"
$previousSdk = $env:UE_SDKS_ROOT
$localSdk = Join-Path $env:LOCALAPPDATA "Codex/UnrealToolchains/WinSDK26100"
try {
    if (-not $previousSdk -and (Test-Path -LiteralPath $localSdk)) {
        $env:UE_SDKS_ROOT = $localSdk
    }
    $cookOption = if ($ReuseCook) { "-skipcook" } else { "-cook" }
    $options = @("BuildCookRun", "-project=$project", "-platform=Win64", "-clientconfig=$Configuration",
        "-map=/Game/AstraTemple/Maps/L_CanopyDeathmatch", $cookOption, "-cookcultures=en",
        "-nop4", "-utf8output", "-unattended", "-AdditionalCookerOptions=-NoAlwaysCookMaps")
    if (!$FullCook) { $options += "-iterate" }
    if (-not $CookOnly) {
        & (Join-Path $PSScriptRoot "Build-Astra.ps1") -Target Both -Configuration $Configuration -EngineRoot $EngineRoot
        $staging = Join-Path $projectRoot "Saved/Deathmatch/Packaging/${Configuration}Stage"
        $options += @("-skipbuild", "-stage", "-pak", "-iostore", "-compressed", "-stagingdirectory=$staging")
        if ($Configuration -eq "Shipping") {
            $options += @("-nodebuginfo", "-prereqs")
            if (-not $StageOnly) {
                $options += @("-archive", "-archivedirectory=$(Join-Path $projectRoot 'Builds')")
            }
        }
    }
    & $uat @options
    if ($LASTEXITCODE -ne 0) { throw "Unreal AutomationTool exited with code $LASTEXITCODE." }
} finally {
    $env:UE_SDKS_ROOT = $previousSdk
}
