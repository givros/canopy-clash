param(
    [ValidateSet("Editor", "Game", "Both")]
    [string]$Target = "Editor",
    [ValidateSet("Development", "Shipping")]
    [string]$Configuration = "Development",
    [string]$EngineRoot
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path $PSScriptRoot -Parent
$project = Join-Path $projectRoot "gameAstraForest.uproject"
$association = (Get-Content -Raw -LiteralPath $project | ConvertFrom-Json).EngineAssociation
if (-not $EngineRoot) {
    $EngineRoot = Join-Path $env:ProgramFiles "Epic Games/UE_$association"
}
$build = Join-Path $EngineRoot "Engine/Build/BatchFiles/Build.bat"
if (-not (Test-Path -LiteralPath $build)) {
    throw "UnrealBuildTool was not found at $build. Supply -EngineRoot for a custom engine installation."
}

$previousSdk = $env:UE_SDKS_ROOT
$localSdk = Join-Path $env:LOCALAPPDATA "Codex/UnrealToolchains/WinSDK26100"
$targets = switch ($Target) {
    "Editor" { "gameAstraForestEditor" }
    "Game"   { "gameAstraForest" }
    "Both"   { "gameAstraForestEditor"; "gameAstraForest" }
}
try {
    if (-not $previousSdk -and (Test-Path -LiteralPath $localSdk)) {
        $env:UE_SDKS_ROOT = $localSdk
    }
    foreach ($name in $targets) {
        $buildConfiguration = if ($name -eq "gameAstraForestEditor") { "Development" } else { $Configuration }
        & $build $name Win64 $buildConfiguration "-Project=$project" -WaitMutex -NoHotReloadFromIDE -NoUBA -MaxParallelActions=5
        if ($LASTEXITCODE -ne 0) {
            throw "UnrealBuildTool exited with code $LASTEXITCODE while building $name."
        }
    }
} finally {
    $env:UE_SDKS_ROOT = $previousSdk
}
