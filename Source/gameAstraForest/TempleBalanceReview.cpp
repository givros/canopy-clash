#if !UE_BUILD_SHIPPING
#include "TempleMatch.h"
#include "TempleFighter.h"
#include "TempleBotController.h"
#include "Navigation/PathFollowingComponent.h"
#include "EngineUtils.h"
#include "Engine/World.h"
#include "Engine/DamageEvents.h"
#include "GameFramework/PlayerStart.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "HAL/PlatformMisc.h"

DEFINE_LOG_CATEGORY_STATIC(LogCanopyBalance,Log,All);
namespace CanopyBalance
{
FDelegateHandle TickHandle;
int32 RoundsWanted=0,RoundNumber=0,PreviousPhase=-1,LastSerial=0;
double RoundStart=0,NextSample=0,FinishedTime=0;
struct FMovementSample
{
    TWeakObjectPtr<ATempleFighter> CurrentPawn;
    FVector Previous=FVector::ZeroVector;
    float Walked=0,Unmoving=0,LongestUnmoving=0;
    int32 Samples=0,LongStops=0;
};
TMap<TWeakObjectPtr<AController>,FMovementSample> Movement;

void Check(UWorld* W)
{
    if(!W || !W->IsGameWorld() || W->GetNetMode()!=NM_DedicatedServer)return;
    auto* Mode=W->GetAuthGameMode<ATempleMatchMode>();
    auto* State=W->GetGameState<ATempleGameState>();
    if(!Mode || !State)return;
    const double Now=W->GetTimeSeconds();
    if(State->Phase==1)LastSerial=0;
    // Capture the winning point too, on the same tick the game mode enters results.
    if(State->Phase==2 || (State->Phase==3 && State->Phase!=PreviousPhase))
    {
        for(const auto& Entry:State->Feed)
        {
            if(Entry.Serial<=LastSerial)continue;
            LastSerial=Entry.Serial;
            FVector AttackerLocation=FVector::ZeroVector,VictimLocation=FVector::ZeroVector;
            bool bFoundAttacker=false,bFoundVictim=false;
            for(TActorIterator<ATempleFighter> It(W);It;++It)
            {
                const auto* PS=It->GetPlayerState<ATemplePlayerState>();
                if(!PS)continue;
                const FString Name=PS->GetPlayerName();
                if(Name==Entry.Victim){VictimLocation=It->GetActorLocation()/100;bFoundVictim=true;}
                if(Name==Entry.Killer){AttackerLocation=It->GetActorLocation()/100;bFoundAttacker=true;}
                if(bFoundVictim && bFoundAttacker)break;
            }
            if(bFoundVictim)
                UE_LOG(LogCanopyBalance,Display,TEXT("CB|contact|%d|%.1f|%d|%s|%.1f|%.1f|%.1f"),RoundNumber,Now-RoundStart,Entry.KillerTeam,*Entry.Victim,VictimLocation.X,VictimLocation.Y,VictimLocation.Z);
            if(bFoundAttacker && bFoundVictim)
                UE_LOG(LogCanopyBalance,Display,TEXT("CB|encounter|%d|%d|%.1f|%.1f|%.1f|%.1f|%.1f|%.1f"),RoundNumber,Entry.KillerTeam,AttackerLocation.X,AttackerLocation.Y,AttackerLocation.Z,VictimLocation.X,VictimLocation.Y,VictimLocation.Z);
        }
    }
    if(State->Phase!=PreviousPhase)
    {
        PreviousPhase=State->Phase;
        if(State->Phase==2){++RoundNumber;RoundStart=Now;Movement.Reset();LastSerial=0;NextSample=Now;}
        if(State->Phase==3)
        {
            FinishedTime=Now;
            UE_LOG(LogCanopyBalance,Display,TEXT("CB|result|%d|%d|%d|%.2f|%d"),RoundNumber,State->RedScore,State->BlueScore,Now-RoundStart,State->PlayerArray.Num());
            for(const auto& Pair:Movement)
            {
                const auto* C=Pair.Key.Get();
                if(!C)continue;
                const auto* PS=C->GetPlayerState<ATemplePlayerState>();
                if(PS)UE_LOG(LogCanopyBalance,Display,TEXT("CB|agent|%d|%s|%d|%d|%d|%.2f|%d|%.1f"),RoundNumber,*PS->GetPlayerName(),PS->Team,PS->Kills,PS->Deaths,Pair.Value.Walked/100,Pair.Value.LongStops,Pair.Value.LongestUnmoving);
            }
        }
    }
    if(State->Phase==3 && Now>FinishedTime+.3)
    {
        if(RoundNumber>=RoundsWanted)FPlatformMisc::RequestExit(false);
        else Mode->Replay();
        return;
    }
    if(State->Phase!=2)return;
    if(Now<NextSample)return;
    NextSample=Now+.5;
    for(TActorIterator<ATempleBotController> It(W);It;++It)
    {
        auto* F=Cast<ATempleFighter>(It->GetPawn());
        if(!F || !F->IsAlive())continue;
        FMovementSample& Sample=Movement.FindOrAdd(*It);
        const FVector P=F->GetActorLocation();
        if(Sample.CurrentPawn.Get()!=F)
        {
            Sample.Previous=P;Sample.CurrentPawn=F;Sample.Unmoving=0;continue;
        }
        const double D=FVector::Dist2D(Sample.Previous,P);
        if(D<1200) Sample.Walked+=D;
        Sample.Previous=P;++Sample.Samples;
        if(Sample.Samples%8==0)
            UE_LOG(LogCanopyBalance,Display,TEXT("CB|position|%d|%.1f|%s|%d|%.1f|%.1f|%.1f"),RoundNumber,Now-RoundStart,*It->PlayerState->GetPlayerName(),F->GetTeam(),P.X/100,P.Y/100,P.Z/100);
        if(It->GetMoveStatus()==EPathFollowingStatus::Moving && D<12)
        {
            Sample.Unmoving+=.5f;
            if(Sample.Unmoving==5)
            {
                ++Sample.LongStops;
                const FVector Goal=It->GetImmediateMoveDestination()/100;
                UE_LOG(LogCanopyBalance,Display,TEXT("CB|slow|%d|%.1f|%s|%.1f|%.1f|%.1f|%.1f|%.1f|%.1f"),RoundNumber,Now-RoundStart,*It->PlayerState->GetPlayerName(),P.X/100,P.Y/100,P.Z/100,Goal.X,Goal.Y,Goal.Z);
            }
            Sample.LongestUnmoving=FMath::Max(Sample.LongestUnmoving,Sample.Unmoving);
        }
        else Sample.Unmoving=0;
    }
}
}
void StartTempleBalanceReview()
{
    if(!FParse::Value(FCommandLine::Get(),TEXT("TempleBalanceRounds="),CanopyBalance::RoundsWanted) || CanopyBalance::RoundsWanted<=0)return;
    int32 Seed;
    if (FParse::Value(FCommandLine::Get(),TEXT("TempleBalanceSeed="),Seed))
    {
        FMath::RandInit(Seed);
        FMath::SRandInit(Seed);
        UE_LOG(LogCanopyBalance,Display,TEXT("CB|seed|%d"),Seed);
    }
    CanopyBalance::TickHandle=FWorldDelegates::OnWorldPostActorTick.AddLambda([](UWorld* World,ELevelTick,float){CanopyBalance::Check(World);});
}
void RecordTempleBalanceImpact(const ATempleFighter* Owner,const FDamageEvent& Event,bool bFatal)
{
    if (!CanopyBalance::RoundsWanted || !Owner || !Event.IsOfType(FPointDamageEvent::ClassID)) return;
    const auto& Hit=static_cast<const FPointDamageEvent&>(Event).HitInfo;
    UE_LOG(LogCanopyBalance,Display,TEXT("CB|impact|%d|%d|%d|%.3f|%.3f|%.3f|%.3f|%.3f|%.3f"),
        CanopyBalance::RoundNumber,Owner->GetTeam(),bFatal,Hit.TraceStart.X/100,Hit.TraceStart.Y/100,Hit.TraceStart.Z/100,
        Hit.ImpactPoint.X/100,Hit.ImpactPoint.Y/100,Hit.ImpactPoint.Z/100);
}
void RecordTempleBalanceSpawn(const ATemplePlayerState* Player,const APlayerStart* Start,float Ally,float Enemy,int32 Visible,bool bRespawn)
{
    if(!CanopyBalance::RoundsWanted || !Player || !Start || !bRespawn)return;
    const FVector P=Start->GetActorLocation()/100.;
    UE_LOG(LogCanopyBalance,Display,TEXT("CB|respawn|%d|%d|%s|%.2f|%.2f|%.2f|%.2f|%d"),
        CanopyBalance::RoundNumber,Player->Team,*Player->GetPlayerName(),P.X,P.Y,
        Ally==FLT_MAX?-1.f:Ally/100.f,Enemy==FLT_MAX?-1.f:Enemy/100.f,Visible);
}
void RecordTempleBaseReturn(const ATemplePlayerState* Player,const FVector& Location)
{
    if (!CanopyBalance::RoundsWanted || !Player) return;
    const FVector P=Location/100.f;
    UE_LOG(LogCanopyBalance,Display,TEXT("CB|safetyreturn|%d|%d|%s|%.2f|%.2f|%.2f"),
        CanopyBalance::RoundNumber,Player->Team,*Player->GetPlayerName(),P.X,P.Y,P.Z);
}
void StopTempleBalanceReview()
{
    if(CanopyBalance::TickHandle.IsValid())FWorldDelegates::OnWorldPostActorTick.Remove(CanopyBalance::TickHandle);
}
#endif
