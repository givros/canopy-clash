param(
    [Parameter(Mandatory=$true)][ValidateSet('Balance','Visual','Profile','Handling','UI')][string]$Kind,
    [Parameter(Mandatory=$true)][ValidatePattern('^[A-Za-z0-9_-]+$')][string]$Name,
    [int]$Rounds=6,[int]$Width=1920,[int]$Height=1080,
    [int]$ScoreLimit=50,[int]$TimeLimit=600,[int]$Port=18037,[int]$ProfileFrames=2100,[int]$TeamSize=5,[switch]$CaptureHandling,[int]$BalanceSeed=0,
    [ValidateScript({(Test-Path -LiteralPath $_ -PathType Leaf) -and [IO.Path]::GetFileName($_) -eq 'L_CanopyDeathmatch.umap'})][string]$MapSnapshot,
    [ValidateScript({(Test-Path -LiteralPath $_ -PathType Leaf) -and [IO.Path]::GetFileName($_) -eq 'UnrealEditor-gameAstraForest.dll'})][string]$ModuleSnapshot,
    [string]$FrozenAssets
)
$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '../../..')).Path
$session=Join-Path $root ('Saved/Deathmatch/'+$Name)
if(Test-Path -LiteralPath $session){throw "Choose a new review name. $session already exists."}
$stage=Join-Path $session 'Runtime'
$bin=Join-Path $stage 'Binaries/Win64'
New-Item -ItemType Directory -Path $bin -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $root 'gameAstraForest.uproject') -Destination $stage
Copy-Item -LiteralPath (Join-Path $root 'Config') -Destination $stage -Recurse
Copy-Item -LiteralPath (Join-Path $root 'Binaries/Win64/UnrealEditor-gameAstraForest.dll'),(Join-Path $root 'Binaries/Win64/UnrealEditor.modules') -Destination $bin
if ($ModuleSnapshot) {
    Copy-Item -LiteralPath $ModuleSnapshot,(Join-Path (Split-Path $ModuleSnapshot -Parent) 'UnrealEditor.modules') -Destination $bin -Force
}
# An uncooked Unreal process can retain a read handle on a mesh until shutdown.
# Give long playtests their own asset snapshot so the open editor can still save.
if ($FrozenAssets) {
    $frozen=(Resolve-Path -LiteralPath $FrozenAssets).Path
    $reviewRoot=(Resolve-Path (Join-Path $root 'Saved/Deathmatch')).Path+[IO.Path]::DirectorySeparatorChar
    if (!$frozen.StartsWith($reviewRoot,[StringComparison]::OrdinalIgnoreCase) -or !(Test-Path (Join-Path $frozen 'AstraTemple/Maps/L_CanopyDeathmatch.umap'))) {
        throw 'FrozenAssets must be a completed asset snapshot in Saved/Deathmatch.'
    }
    # Share immutable assets between game-only runs. Each instance has private maps and writable state.
    $content=New-Item -ItemType Directory -Path (Join-Path $stage 'Content')
    foreach ($group in (Get-ChildItem -LiteralPath $frozen)) {
        if ($group.Name -eq 'AstraTemple') {
            $temple=New-Item -ItemType Directory -Path (Join-Path $content.FullName $group.Name)
            foreach ($asset in (Get-ChildItem -LiteralPath $group.FullName)) {
                if ($asset.PSIsContainer -and $asset.Name -ne 'Maps') {
                    New-Item -ItemType Junction -Path (Join-Path $temple.FullName $asset.Name) -Target $asset.FullName | Out-Null
                } else { Copy-Item -LiteralPath $asset.FullName -Destination $temple.FullName -Recurse }
            }
        } elseif ($group.PSIsContainer) {
            New-Item -ItemType Junction -Path (Join-Path $content.FullName $group.Name) -Target $group.FullName | Out-Null
        } else { Copy-Item -LiteralPath $group.FullName -Destination $content.FullName }
    }
} else { Copy-Item -LiteralPath (Join-Path $root 'Content') -Destination $stage -Recurse }
if ($MapSnapshot) {
    Copy-Item -LiteralPath $MapSnapshot -Destination (Join-Path $stage 'Content/AstraTemple/Maps/L_CanopyDeathmatch.umap') -Force
}
$project=Join-Path $stage 'gameAstraForest.uproject'
$exe=Join-Path $env:ProgramFiles 'Epic Games/UE_5.9/Engine/Binaries/Win64/UnrealEditor.exe'
if($Kind -eq 'Handling'){$TeamSize=1}
$map="/Game/AstraTemple/Maps/L_CanopyDeathmatch?ScoreLimit=${ScoreLimit}?TimeLimit=${TimeLimit}?TeamSize=${TeamSize}"
$options=@($project,$map,'-game','-NoSplash','-NoSound','-NoLiveCoding','-NoSourceControl','-NoEpicPortal','-Unattended','-NoCrashDialog','-NoTurnkey','-ini:EditorPerProjectUserSettings:[/Script/ModelContextProtocol.ModelContextProtocolSettings]:bAutoStartServer=False',('-AbsLog='+$session+'/Review.log'))
if($Kind -eq 'Balance'){
    $options+=@('-server','-nullrhi','-multihome=127.0.0.1',('-port='+$Port),('-TempleBalanceRounds='+$Rounds),'-UseFixedTimeStep','-FPS=30','-benchmark')
    if ($PSBoundParameters.ContainsKey('BalanceSeed')) { $options+=('-TempleBalanceSeed='+$BalanceSeed) }
} elseif($Kind -eq 'Handling') {
    $options+=@('-RenderOffscreen','-Windowed','-TempleHandlingReview','-UseFixedTimeStep','-FPS=60','-benchmark')
    if($CaptureHandling){$options+=@('-ForceRes',('-ResX='+$Width),('-ResY='+$Height),('-TempleHandlingImages='+$session))}
    else{$options+='-nullrhi'}
} elseif($Kind -eq 'UI') {
    $options+=@('-RenderOffscreen','-Windowed','-ForceRes',('-ResX='+$Width),('-ResY='+$Height),('-TempleUIAudit='+$session+'/UIInput.json'))
} else {
    $options+=@('-RenderOffscreen','-Windowed','-ForceRes',('-ResX='+$Width),('-ResY='+$Height),('-TempleVisualReview='+$session))
    if($Kind -eq 'Profile'){
        $options=@($options | Where-Object {$_ -ne '-NoSound'})
        $options+=@('-AudioMixer','-DeterministicAudio','-csvGpuStats','-csvCompression=0','-TempleMeasure',('-TempleMeasureFrames='+$ProfileFrames),'-ExitAfterCsvProfiling')
    }
}
$previousSdkCheck=$env:UE_SKIP_UBT_SDK_SETUP
try {
    # A game running an already-built module needs no SDK discovery or build lock.
    $env:UE_SKIP_UBT_SDK_SETUP='1'
    $game=Start-Process -FilePath $exe -ArgumentList $options -WorkingDirectory $stage -WindowStyle Hidden -PassThru
} finally {
    $env:UE_SKIP_UBT_SDK_SETUP=$previousSdkCheck
}
[pscustomobject]@{Process=$game.Id;Session=$session;Kind=$Kind} | ConvertTo-Json -Compress
