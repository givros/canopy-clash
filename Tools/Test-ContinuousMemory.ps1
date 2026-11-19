param(
    [Parameter(Mandatory=$true)][string]$ReplayCsv,
    [string]$BuildDirectory = (Join-Path (Split-Path $PSScriptRoot -Parent) "Saved/Deathmatch/Packaging/DevelopmentStage/Windows")
)

$ErrorActionPreference = "Stop"
$rounds = @(Import-Csv -LiteralPath $ReplayCsv | Where-Object stage -eq "replay_post_gc")
if ($rounds.Count -ne 8) { throw "Provide a completed eight-round replay CSV." }
$stage = (Resolve-Path -LiteralPath $BuildDirectory).Path
$runtime = (Resolve-Path -LiteralPath (Join-Path $stage "gameAstraForest/Binaries/Win64/gameAstraForest.exe")).Path
$output = Join-Path (Split-Path (Resolve-Path -LiteralPath $ReplayCsv).Path -Parent) "ContinuousControl"
New-Item -ItemType Directory -Path $output -Force | Out-Null
$log = Join-Path $output "WindowsGame.log"
$seconds = [math]::Ceiling([double]::Parse($rounds[-1].world_seconds, [cultureinfo]::InvariantCulture)) + 20
$options = @(
    "/Game/AstraTemple/Maps/L_CanopyDeathmatch?ScoreLimit=1000?TimeLimit=600",
    "-RenderOffscreen", "-Windowed", "-ForceRes", "-ResX=960", "-ResY=540",
    "-NoSplash", "-NoCrashDialog", "-NoMessaging", "-Unattended", "-DeterministicAudio",
    '-ExecCmds="t.MaxFPS 24,DisableAllScreenMessages"', "-SECONDS=$seconds", "-AbsLog=`"$log`""
)
$game = Start-Process -FilePath $runtime -ArgumentList $options -PassThru -WindowStyle Hidden -WorkingDirectory $stage
$records = New-Object 'System.Collections.Generic.List[object]'
try {
    $deadline = [DateTime]::UtcNow.AddSeconds(55)
    do {
        if ($game.HasExited) { throw "Continuous game exited before map start with code $($game.ExitCode)." }
        if ([DateTime]::UtcNow -gt $deadline) { throw "The cooked map failed to begin play." }
        Start-Sleep -Milliseconds 300
    } while (!(Test-Path -LiteralPath $log) -or !(Select-String -LiteralPath $log -Pattern 'Bringing World .*L_CanopyDeathmatch.* up for play' -Quiet))

    $clock = [Diagnostics.Stopwatch]::StartNew()
    foreach ($round in $rounds) {
        $targetTime = [double]::Parse($round.world_seconds, [cultureinfo]::InvariantCulture)
        while ($clock.Elapsed.TotalSeconds -lt $targetTime) {
            if ($game.HasExited) { throw "Continuous game exited before checkpoint $($round.round)." }
            Start-Sleep -Milliseconds 200
        }
        $game.Refresh()
        $records.Add([ordered]@{
            checkpoint = [int]$round.round
            elapsed_seconds = [math]::Round($clock.Elapsed.TotalSeconds,2)
            private_commit_mib = [math]::Round($game.PrivateMemorySize64 / 1MB,2)
            working_set_mib = [math]::Round($game.WorkingSet64 / 1MB,2)
        })
    }
    if (!$game.WaitForExit(65000)) { throw "Continuous game did not exit at its configured time." }
    if ($game.ExitCode -ne 0) { throw "Continuous game exited with code $($game.ExitCode)." }
    [ordered]@{
        mode = "Single uninterrupted 5v5 match, default garbage collection"
        replay_csv = (Resolve-Path -LiteralPath $ReplayCsv).Path
        executable = $runtime
        exit_code = $game.ExitCode
        samples = $records
    } | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $output "Control.json") -Encoding UTF8
    $records | ForEach-Object { [pscustomobject]$_ } | Format-Table -AutoSize
} finally {
    if (!$game.HasExited) { $game.Kill(); $game.WaitForExit() }
}
