#if !UE_BUILD_SHIPPING
#include "TempleMatch.h"
#include "TempleFighter.h"
#include "TempleBotController.h"
#include "TempleDeploymentNavigation.h"
#include "AIController.h"
#include "Components/CapsuleComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/DamageEvents.h"
#include "Engine/Engine.h"
#include "Engine/NetConnection.h"
#include "Engine/NetDriver.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/PlayerState.h"
#include "HAL/PlatformMisc.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "NavigationPath.h"
#include "NavigationSystem.h"
#include "UnrealClient.h"

DEFINE_LOG_CATEGORY_STATIC(LogTempleAudit, Log, All);

namespace
{
FDelegateHandle AuditTick;
FString AuditRole;

void InspectCookedDeploymentPaths(UWorld* World)
{
    auto* Mode = World->GetAuthGameMode<ATempleMatchMode>();
    if (!Mode) return;
    const FVector Extent(190, 190, 450);
    const auto Project = [&](const FVector& Point, FVector& Ground)
    {
        return UNavigationSystemV1::K2_ProjectPointToNavigation(World, Point, Ground, nullptr, nullptr, Extent);
    };
    FVector Goal;
    if (!Project(FVector(3100, 0, 1200), Goal)) return;
    const double HalfHeight = GetDefault<ATempleFighter>()->GetCapsuleComponent()->GetUnscaledCapsuleHalfHeight();
    TArray<FVector> Starts = {FVector(-700, 2170, 400), FVector(1100, 3900, 440), FVector(1200, -2300, 400)};
    for (uint8 Team = 0; Team < 2; ++Team)
    {
        ATempleBotController* Bot = nullptr;
        for (TActorIterator<ATempleBotController> It(World); It; ++It)
        {
            const auto* Side = It->GetPlayerState<ATemplePlayerState>();
            if (Side && Side->Team == Team && It->GetPawn()) { Bot = *It; break; }
        }
        if (!Bot) continue;
        for (int32 Index = 0; Index < Starts.Num(); ++Index)
        {
            FVector Origin;
            if (!Project(Starts[Index], Origin)) continue;
            const auto Filter = Bot->GetDefaultNavigationFilterClass();
            const UNavigationPath* Path = UNavigationSystemV1::FindPathToLocationSynchronously(World, Origin, Goal, Bot, Filter);
            const bool Complete = Path && Path->IsValid() && !Path->IsPartial();
            int32 Intrusions = 0;
            if (Complete)
            {
                for (int32 Point = 1; Point < Path->PathPoints.Num(); ++Point)
                {
                    const FVector A = Path->PathPoints[Point-1], B = Path->PathPoints[Point];
                    const int32 Steps = FMath::Max(1, int32(FMath::CeilToInt(FVector::Distance(A,B) / 5.)));
                    for (int32 Step = 0; Step <= Steps; ++Step)
                    {
                        const FVector Capsule = FMath::Lerp(A, B, double(Step)/Steps) + FVector(0,0,HalfHeight);
                        Intrusions += Mode->IsEnemySafeZone(Team, Capsule) ? 1 : 0;
                    }
                }
            }
            UE_LOG(LogTempleAudit, Display, TEXT("TQA|baked_route|%u|%d|%s|%d|%d|%.2f"),
                   Team, Index, *GetNameSafe(Filter.Get()), Complete ? 1 : 0, Intrusions, Path ? Path->GetPathLength()/100. : 0.);
        }
    }
}

struct FTrackedFighter
{
    TWeakObjectPtr<ATempleFighter> Pawn;
    FVector LastLocation = FVector::ZeroVector;
    float Walked = 0.f;
    float RespawnAt = 0.f;
    int32 Respawns = 0;
};
class FTempleAudit
{
    TMap<int32,FTrackedFighter> Tracked;
    int32 Phase = INDEX_NONE, Round = 0, FeedSerial = 0;
    int32 StandingsRound=INDEX_NONE;
    double PhaseAt = 0, NextSample = 0, NextReport = 0;
    bool FriendlyChecked = false, RulesAdjusted = false, SentReplay = false, Finished = false;
    int32 Stage = 0, OriginalTeam = -1, IntendedTeam = -1, InitialAmmo = 0, InitialReserve = 0, LowestAmmo = 10000;
    float ActionAt = 0;
    bool SawReload = false, SawAim = false, SawScoreboard = false;
    TWeakObjectPtr<ATempleFighter> OperatingPawn;
    FVector InputOrigin = FVector::ZeroVector;

    void ObserveClients(ATempleGameState* State, UWorld* World)
    {
        int32 Sides[2]={}, Humans=0;
        const bool bCheckBotRoster = FParse::Param(FCommandLine::Get(), TEXT("TempleBotRosterAudit"));
        for(APlayerState* Item:State->PlayerArray)
        {
            if(auto* PS=Cast<ATemplePlayerState>(Item); PS && PS->Team<2)
            {
                ++Sides[PS->Team];
                if (bCheckBotRoster)
                {
                    const ATempleFighter* Pawn = Cast<ATempleFighter>(PS->GetPawn());
                    const USkeletalMeshComponent* Body = Pawn ? Pawn->GetBotPresentationBody() : nullptr;
                    UE_LOG(LogTempleAudit, Display, TEXT("TQA|bot_roster|%s|%.3f|%d|%d|%d|%d|%d|%s|%s|%s|%s|%d"),
                        *AuditRole, State->GetServerWorldTimeSeconds(), static_cast<int32>(World->GetNetMode()),
                        PS->GetPlayerId(), PS->Team, PS->IsABot(), Pawn && Pawn->IsLocallyControlled(),
                        *GetNameSafe(Pawn), Pawn ? *Pawn->GetBotAppearanceName().ToString() : TEXT("None"),
                        *GetNameSafe(Body ? Body->GetOwner()->GetClass() : nullptr),
                        *GetNameSafe(Body ? Body->GetSkeletalMeshAsset() : nullptr), Pawn && Pawn->GetMesh()->IsVisible());
                }
                if (!PS->IsABot())
                {
                    ++Humans;
                    if (FParse::Param(FCommandLine::Get(), TEXT("TempleInspectNames")))
                    {
                        UE_LOG(LogTempleAudit, Display, TEXT("TQA|human_name|%s|%d|%s"), *AuditRole, PS->GetPlayerId(), *PS->GetPlayerName());
                    }
                }
            }
        }
        const auto* Net=World->GetNetDriver();
        const int32 Links=Net?(Net->ServerConnection?1:Net->ClientConnections.Num()):0;
        UE_LOG(LogTempleAudit,Display,TEXT("TQA|snapshot|%s|%d|%d|%.2f|%d|%d|%d|%d|%d|%d|%d|%.2f"),*AuditRole,Round,State->Phase,State->GetServerWorldTimeSeconds(),State->RedScore,State->BlueScore,Sides[0],Sides[1],Humans,Links,State->ScoreLimit,State->PhaseEndsAt);
    }
    void ObserveFighters(UWorld* World, ATempleMatchMode* Mode)
    {
        TArray<ATempleFighter*> Live;
        for(FConstControllerIterator It=World->GetControllerIterator();It;++It)
        {
            auto* C=It->Get();auto* PS=C?C->GetPlayerState<ATemplePlayerState>():nullptr;
            if(!PS || PS->Team>1)continue;
            auto& Record=Tracked.FindOrAdd(PS->GetUniqueID());
            auto* F=Cast<ATempleFighter>(C->GetPawn());
            if(PS->RespawnAt>0)Record.RespawnAt=PS->RespawnAt;
            if(!F || !F->IsAlive())continue;
            Live.Add(F);
            const FVector Location=F->GetActorLocation();
            if(Record.Pawn.Get()==F)
            {
                float Step=FVector::Distance(Location,Record.LastLocation);
                // Exclude spawn teleports while measuring physical in-match movement.
                if(Step<400.f) Record.Walked+=Step;
            }
            else if(Record.RespawnAt>0 && PS->RespawnAt==0)
            {
                ++Record.Respawns;
                UE_LOG(LogTempleAudit,Display,TEXT("TQA|respawn|%d|%u|%.3f|%.3f"),Round,PS->GetUniqueID(),Record.RespawnAt,World->GetTimeSeconds());
                Record.RespawnAt=0;
            }
            Record.Pawn=F; Record.LastLocation=Location;
        }
        if(FriendlyChecked || !Mode->IsCombatActive())return;
        for(ATempleFighter* Victim:Live)
        {
            if(Victim->IsSpawnProtected())continue;
            for(ATempleFighter* Ally:Live)
            {
                if(Ally==Victim || Ally->GetTeam()!=Victim->GetTeam())continue;
                const float Before=Victim->GetHealth();
                if(Mode->bFriendlyFire)
                {
                    auto* State=World->GetGameState<ATempleGameState>();
                    const auto* VictimState=Victim->GetPlayerState<ATemplePlayerState>();
                    const auto* AllyState=Ally->GetPlayerState<ATemplePlayerState>();
                    const int32 Red=State->RedScore,Blue=State->BlueScore,Kills=AllyState->Kills,Deaths=VictimState->Deaths;
                    const float Given=Victim->TakeDamage(Before,FDamageEvent(),Ally->GetController(),Ally);
                    UE_LOG(LogTempleAudit,Display,TEXT("TQA|friendly_enabled|%.2f|%.2f|%.2f|%d|%d|%d|%d"),Before,Given,Victim->GetHealth(),State->RedScore-Red,State->BlueScore-Blue,AllyState->Kills-Kills,VictimState->Deaths-Deaths);
                    FriendlyChecked=true;return;
                }
                const float Applied=Victim->TakeDamage(11.f,FDamageEvent(),Ally->GetController(),Ally);
                UE_LOG(LogTempleAudit,Display,TEXT("TQA|friendly_probe|%.3f|%.3f|%.3f|%d"),Before,Victim->GetHealth(),Applied,Victim->IsSpawnProtected()?1:0);
                FriendlyChecked=true;return;
            }
        }
    }
    void HumanActions(ATemplePlayerController* PC,ATempleGameState* State,double Now)
    {
        auto* PS=PC->GetPlayerState<ATemplePlayerState>();
        if(!PS || PS->Team>1)return;
        if(Stage==0)
        {
            OriginalTeam=PS->Team;IntendedTeam=1-OriginalTeam;
            PC->JoinTeam(IntendedTeam);Stage=1;ActionAt=Now;
        }
        if(Stage==1 && PS->Team==IntendedTeam)
        {
            UE_LOG(LogTempleAudit,Display,TEXT("TQA|team_rpc|%s|%d|%d"),*AuditRole,OriginalTeam,PS->Team);Stage=2;
        }
        if(Stage<2 || Stage>=7 || State->Phase!=2)return;
        auto* F=Cast<ATempleFighter>(PC->GetPawn());
        if(!F || !F->IsAlive() || F->IsSpawnProtected())return;
        if(Stage>2 && OperatingPawn.Get()!=F){Stage=2;}
        if(Stage==2)
        {
            OperatingPawn=F;InitialAmmo=F->GetMagazineAmmo();InitialReserve=F->GetReserveAmmo();
            if(InitialAmmo<5)return;
            LowestAmmo=InitialAmmo;SawAim=SawReload=false;
            PC->SetScoreboardVisible(true);SawScoreboard=PC->bScoreboardVisible;PC->SetScoreboardVisible(false);
            InputOrigin=F->GetActorLocation();
            PC->SetControlRotation(FRotator(65.f,PC->GetControlRotation().Yaw,0));
            F->SetAiming(true);F->SetTriggerHeld(true);ActionAt=Now;Stage=3;
        }
        if(Stage==3)
        {
            F->AddMovementInput(F->GetActorForwardVector(),1.f);
            SawAim|=F->IsAiming();LowestAmmo=FMath::Min(LowestAmmo,F->GetMagazineAmmo());
            if(Now-ActionAt>.72){
                F->SetTriggerHeld(false);F->SetAiming(false);Stage=4;ActionAt=Now;
            }
        }
        if(Stage==4 && Now-ActionAt>.35)
        {
            LowestAmmo=FMath::Min(LowestAmmo,F->GetMagazineAmmo());
            F->StartReload();ActionAt=Now;Stage=5;
        }
        if(Stage==5)
        {
            SawReload|=F->IsReloading();
            if(Now-ActionAt>3.4)
            {
                UE_LOG(LogTempleAudit,Display,TEXT("TQA|controls|%s|%d|%d|%d|%d|%d|%d|%d|%d|%.2f"),*AuditRole,InitialAmmo,LowestAmmo,F->GetMagazineAmmo(),InitialReserve,F->GetReserveAmmo(),SawAim?1:0,SawReload?1:0,SawScoreboard?1:0,FVector::Distance(InputOrigin,F->GetActorLocation()));
                Stage=7;
            }
        }
    }
public:
    void Tick(UWorld* World)
    {
        auto* S=World->GetGameState<ATempleGameState>();
        if(!S || Finished)return;
        const double Now=S->GetServerWorldTimeSeconds();
        if(Phase!=S->Phase)
        {
            if(!Round || (Phase==3 && S->Phase!=3))++Round;
            Phase=S->Phase;PhaseAt=Now;SentReplay=false;
            UE_LOG(LogTempleAudit,Display,TEXT("TQA|phase|%s|%d|%d|%.2f|%d|%d|%u|%d"),*AuditRole,Round,Phase,Now,S->RedScore,S->BlueScore,S->WinnerTeam,S->ScoreLimit);
            ObserveClients(S,World);
        }
        if(Now>=NextReport){NextReport=Now+5;ObserveClients(S,World);}
        if(Phase==3 && StandingsRound!=Round && !S->FinalStandings.IsEmpty())
        {
            const APlayerController* Local=World->GetFirstPlayerController();
            const int32 LocalId=Local && Local->PlayerState?Local->PlayerState->GetPlayerId():INDEX_NONE;
            if(World->GetNetMode()==NM_Client && LocalId==INDEX_NONE)return;
            StandingsRound=Round;
            for(const FTempleStanding& Row:S->FinalStandings)
                UE_LOG(LogTempleAudit,Display,TEXT("TQA|final_row|%s|%d|%d|%d|%d|%d|%s"),*AuditRole,Round,Row.PlayerId,Row.Team,Row.Kills,Row.Deaths,*Row.Name);
            UE_LOG(LogTempleAudit,Display,TEXT("TQA|final_viewer|%s|%d|%d|%d"),*AuditRole,Round,LocalId,S->FinalStandings.Num());
        }
        const bool Authority=AuditRole==TEXT("server");
        if(Authority && Now>=NextSample)
        {
            NextSample=Now+.12;
            if(auto* Mode=World->GetAuthGameMode<ATempleMatchMode>())ObserveFighters(World,Mode);
        }
        for(const FTempleFeedEntry& E:S->Feed)
        {
            if(E.Serial<=FeedSerial)continue;
            FeedSerial=E.Serial;
            UE_LOG(LogTempleAudit,Display,TEXT("TQA|kill|%s|%d|%d|%s|%s|%u|%u|%.2f"),*AuditRole,Round,E.Serial,*E.Killer,*E.Victim,E.KillerTeam,E.VictimTeam,E.ServerTime);
        }
        if(!Authority)
        {
            if(auto* PC=Cast<ATemplePlayerController>(World->GetFirstPlayerController()))
            {
                HumanActions(PC,S,Now);
                if(AuditRole==TEXT("red") && Round==1 && Phase==3 && !SentReplay && Now-PhaseAt>5.0)
                {
                    PC->ReplayMatch();SentReplay=true;
                    UE_LOG(LogTempleAudit,Display,TEXT("TQA|replay_rpc|red"));
                }
            }
        }
        else if(Round==1 && Phase==3 && !RulesAdjusted)
        {
            if(auto* M=World->GetAuthGameMode<ATempleMatchMode>())
            {
                const bool ByScore=FMath::Max(S->RedScore,S->BlueScore)>=S->ScoreLimit;
                // Exercise the other termination path in a separate round. Default game rules are untouched outside the audit process.
                M->ScoreTarget=ByScore?500:2;M->MatchDuration=ByScore?24.f:165.f;RulesAdjusted=true;
                UE_LOG(LogTempleAudit,Display,TEXT("TQA|next_round_rules|%d|%.1f"),M->ScoreTarget,M->MatchDuration);
            }
        }
        if(Round>=2 && Phase==3 && Now-PhaseAt>(Authority?7.:4.))
        {
            if(Authority)
            {
                float Meters=0;int32 Mobile=0,Respawns=0;
                for(const auto& KV:Tracked){Meters+=KV.Value.Walked*.01f;Respawns+=KV.Value.Respawns;if(KV.Value.Walked>400.f)++Mobile;}
                UE_LOG(LogTempleAudit,Display,TEXT("TQA|movement|%d|%.2f|%d"),Mobile,Meters,Respawns);
            }
            UE_LOG(LogTempleAudit,Display,TEXT("TQA|done|%s"),*AuditRole);
            Finished=true;FPlatformMisc::RequestExit(false);
        }
    }
};
TUniquePtr<FTempleAudit> Observer;
}
void StartTempleMatchAudit()
{
    FString PreviewPath;
    if (FParse::Value(FCommandLine::Get(), TEXT("TempleCapture="), PreviewPath))
    {
        AuditTick = FWorldDelegates::OnWorldPostActorTick.AddLambda(
            [PreviewPath, RequestedAt = -1.f](UWorld* World, ELevelTick, float) mutable
            {
                if (!World || !World->IsGameWorld() || !World->GetMapName().Contains(TEXT("L_CanopyDeathmatch"))) return;
                const ATempleGameState* State = World->GetGameState<ATempleGameState>();
                if (!State || State->Phase != 2 || World->GetTimeSeconds() < 12.f) return;
                if (RequestedAt < 0)
                {
                    RequestedAt = World->GetTimeSeconds();
                    for (const TCHAR* Command : {TEXT("getall TemplePlayerState Team"), TEXT("getall TempleFighter Health"),
                         TEXT("getall TempleGameState Phase"), TEXT("getall TempleGameState RedScore"), TEXT("getall TempleGameState BlueScore")})
                    {
                        GEngine->Exec(World, Command);
                    }
                    InspectCookedDeploymentPaths(World);
                    FScreenshotRequest::RequestScreenshot(PreviewPath, true, false);
                    UE_LOG(LogTempleAudit, Display, TEXT("TQA|packaged_capture|requested"));
                }
                if (World->GetTimeSeconds() > RequestedAt + 1.f && !FScreenshotRequest::IsScreenshotRequested())
                {
                    UE_LOG(LogTempleAudit, Display, TEXT("TQA|packaged_capture|complete"));
                    FPlatformMisc::RequestExit(false);
                }
            });
        return;
    }
    if(!FParse::Value(FCommandLine::Get(),TEXT("TempleMatchAudit="),AuditRole) || (AuditRole!=TEXT("server") && AuditRole!=TEXT("red") && AuditRole!=TEXT("blue")))return;
    AuditTick=FWorldDelegates::OnWorldPostActorTick.AddLambda([](UWorld* World,ELevelTick,float)
    {
        if(!World || !World->IsGameWorld() || !World->HasBegunPlay() || !World->GetMapName().Contains(TEXT("L_CanopyDeathmatch")))return;
        if(AuditRole!=TEXT("server") && World->GetNetMode()!=NM_Client)return;
        if(!Observer)Observer=MakeUnique<FTempleAudit>();
        Observer->Tick(World);
    });
}
void StopTempleMatchAudit()
{
    if(AuditTick.IsValid())FWorldDelegates::OnWorldPostActorTick.Remove(AuditTick);
    Observer.Reset();
}
#endif
