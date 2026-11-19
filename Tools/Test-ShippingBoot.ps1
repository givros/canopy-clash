param(
    [string]$BuildDirectory = (Join-Path (Split-Path $PSScriptRoot -Parent) "Builds/Windows")
)

$ErrorActionPreference = "Stop"
$archive = (Resolve-Path -LiteralPath $BuildDirectory).Path
$launcher = Join-Path $archive "gameAstraForest.exe"
$game = (Resolve-Path -LiteralPath (Join-Path $archive "gameAstraForest/Binaries/Win64/gameAstraForest-Win64-Shipping.exe")).Path
$evidence = Join-Path (Split-Path $PSScriptRoot -Parent) "Saved/Deathmatch/Packaging"
$record = Join-Path $evidence ("ShippingBoot_{0}.json" -f (Get-Date -Format "yyyyMMdd_HHmmss"))
$process = Start-Process -FilePath $launcher -ArgumentList @(
    "-RenderOffscreen", "-Windowed", "-ResX=1280", "-ResY=720", "-ForceRes",
    "-Unattended", "-NoSplash", "-NoSound", "-NoMessaging", "-NoCrashDialog"
) -WorkingDirectory $archive -WindowStyle Hidden -PassThru

$child = $null
try {
    $deadline = (Get-Date).AddSeconds(60)
    do {
        if ($process.HasExited) { throw "The Shipping bootstrap exited with code $($process.ExitCode)." }
        $child = Get-CimInstance Win32_Process -Filter "ParentProcessId=$($process.Id)" |
            Where-Object { $_.ExecutablePath -eq $game } | Select-Object -First 1
        if (!$child) { Start-Sleep -Milliseconds 400 }
    } while (!$child -and (Get-Date) -lt $deadline)
    if (!$child) { throw "The packaged Shipping process was not observed." }

    Start-Sleep -Seconds 20
    $first = Get-Process -Id $child.ProcessId
    $firstCpu = $first.TotalProcessorTime.TotalSeconds
    Start-Sleep -Seconds 5
    $running = Get-Process -Id $child.ProcessId
    $gpu = Get-CimInstance Win32_PerfFormattedData_GPUPerformanceCounters_GPUProcessMemory |
        Where-Object { $_.Name -like "pid_$($running.Id)_*" }
    $graphicsMemory = ($gpu | Measure-Object -Property DedicatedUsage -Sum).Sum
    $d3d = @($running.Modules | Where-Object { $_.ModuleName -ieq "d3d12core.dll" }).Count -gt 0
    $gameSocket = @(Get-NetUDPEndpoint -OwningProcess $running.Id -LocalPort 7777 -ErrorAction SilentlyContinue)
    $cpuDelta = $running.TotalProcessorTime.TotalSeconds - $firstCpu
    $result = [ordered]@{
        passed = $d3d -and $graphicsMemory -gt 134217728 -and $cpuDelta -gt 0 -and $gameSocket.Count -eq 0
        bootstrap = $launcher
        executable = $running.Path
        process_window_title_if_reported = $running.MainWindowTitle
        pid = $running.Id
        d3d12_loaded = $d3d
        dedicated_gpu_bytes = $graphicsMemory
        working_set_bytes = $running.WorkingSet64
        cpu_seconds_in_sample = $cpuDelta
        game_port_7777_sockets = $gameSocket.Count
        exit_method = "Test stopped its own process after measurement."
    }
    $result | ConvertTo-Json | Set-Content -LiteralPath $record -Encoding utf8
    $result | ConvertTo-Json
    if (!$result.passed) { throw "The Shipping graphics startup check failed. See $record" }
} finally {
    $children = Get-CimInstance Win32_Process -Filter "ParentProcessId=$($process.Id)" |
        Where-Object { $_.ExecutablePath -eq $game }
    foreach ($item in $children) {
        $owned = Get-Process -Id $item.ProcessId -ErrorAction SilentlyContinue
        if ($owned -and $owned.Path -eq $game) { Stop-Process -InputObject $owned }
    }
    if (!$process.HasExited -and !$process.WaitForExit(10000)) { $process.Kill() }
}
