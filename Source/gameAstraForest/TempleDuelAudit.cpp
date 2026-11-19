#if !UE_BUILD_SHIPPING
#include "TempleMatch.h"
#include "TempleFighter.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "Components/CapsuleComponent.h"
#include "HAL/PlatformMisc.h"
#include "Misc/CommandLine.h"

DEFINE_LOG_CATEGORY_STATIC(LogTempleDuel,Log,All);

namespace
{
FString DuelRole;
FDelegateHandle DuelHandle;
struct FControlledEncounter
{
    bool Setup=false,DeadSeen=false,Finished=false,Firing=false,FirstBurst=false,SecondBurst=false,FirstContact=false;
    float SetupAt=0,ReleaseAt=0,EndAt=0,LowestHP=100,VictimPrevious=100,OriginalHitTime=0;
    bool bCheckFlick=FParse::Param(FCommandLine::Get(),TEXT("TempleFlick")),bRecordedFlick=false;
    int32 AtSetupScore=0,AtSetupDeaths=0,AtSetupKills=0;
    TWeakObjectPtr<ATempleFighter> Bodies[2],LocalOriginal,Opponent;
    TWeakObjectPtr<ATemplePlayerState> Competitors[2],Defender;
    float SeenHP[2]={100,100};
    bool Seat(UWorld* W,ATempleFighter* F,const FVector2D XY,const float Yaw)
    {
        FHitResult Hit;FCollisionQueryParams Q(SCENE_QUERY_STAT(TempleControlledDuel),true,F);
        if(!W->LineTraceSingleByChannel(Hit,FVector(XY.X,XY.Y,850),FVector(XY.X,XY.Y,-110),ECC_Visibility,Q))return false;
        const FVector P=Hit.ImpactPoint+FVector(0,0,F->GetCapsuleComponent()->GetScaledCapsuleHalfHeight()+2);
        const FRotator R(0,Yaw,0);
        F->GetCharacterMovement()->StopMovementImmediately();
        if(!F->TeleportTo(P,R))return false;
        F->GetController()->SetControlRotation(R);F->ForceNetUpdate();return true;
    }
    void Server(UWorld* W,ATempleGameState* G,float Now)
    {
        if(!Setup)
        {
            if(G->Phase!=2 || G->PlayerArray.Num()!=2)return;
            TArray<ATempleFighter*> Found;
            for(FConstPlayerControllerIterator It=W->GetPlayerControllerIterator();It;++It)
                if(auto* C=It->Get())if(auto* F=Cast<ATempleFighter>(C->GetPawn());F && F->IsAlive() && !F->IsSpawnProtected())Found.Add(F);
            if(Found.Num()!=2 || Found[0]->GetTeam()==Found[1]->GetTeam())return;
            if(!Seat(W,Found[0],FVector2D(-3640,1767),8)||!Seat(W,Found[1],FVector2D(-2940,1868),-172))return;
            for(int32 Idx=0;Idx<2;++Idx){Bodies[Idx]=Found[Idx];Competitors[Idx]=Found[Idx]->GetPlayerState<ATemplePlayerState>();SeenHP[Idx]=Found[Idx]->GetHealth();}
            AtSetupScore=G->RedScore+G->BlueScore;Setup=true;SetupAt=Now;
            UE_LOG(LogTempleDuel,Display,TEXT("TQD|setup|server|%.2f|%u|%u|%.1f|%d"),Now,Found[0]->GetTeam(),Found[1]->GetTeam(),FVector::Dist(Found[0]->GetActorLocation(),Found[1]->GetActorLocation()),AtSetupScore);
        }
        for(int32 Idx=0;Idx<2;++Idx)
        {
            auto* F=Bodies[Idx].Get();auto* PS=Competitors[Idx].Get();
            if(!PS)continue;
            if(F && F->GetHealth()<SeenHP[Idx])
            {
                UE_LOG(LogTempleDuel,Display,TEXT("TQD|hit|server|%u|%.1f|%.1f|%.2f"),F->GetTeam(),SeenHP[Idx],F->GetHealth(),Now);
                SeenHP[Idx]=F->GetHealth();
                if(!F->IsAlive()){Defender=PS;DeadSeen=true;UE_LOG(LogTempleDuel,Display,TEXT("TQD|death|server|%d|%.2f|%.2f"),PS->Deaths,Now,PS->RespawnAt);}
            }
            if(DeadSeen && Defender.Get()==PS && !EndAt && PS->RespawnAt==0)
            {
                ATempleFighter* New=Cast<ATempleFighter>(PS->GetPawn());
                if(New && New!=F && New->IsAlive())
                {
                    EndAt=Now+4;
                    UE_LOG(LogTempleDuel,Display,TEXT("TQD|respawn|server|%.1f|%d|%d|%d|%.2f"),New->GetHealth(),G->RedScore+G->BlueScore-AtSetupScore,New->IsSpawnProtected()?1:0,PS->Deaths,Now);
                }
            }
        }
    }
    void Client(UWorld* W,ATempleGameState* G,float Now)
    {
        auto* PC=Cast<ATemplePlayerController>(W->GetFirstPlayerController());
        if(!PC)return;
        auto* F=Cast<ATempleFighter>(PC->GetPawn());auto* PS=PC->GetPlayerState<ATemplePlayerState>();
        if(!PS)return;
        if(!Setup)
        {
            if(!F || !F->IsAlive() || FMath::Abs(F->GetActorLocation().X+3290)>450 || FMath::Abs(F->GetActorLocation().Y-1810)>160)return;
            for(TActorIterator<ATempleFighter> It(W);It;++It)
            {
                if(*It==F || !It->IsAlive() || It->GetTeam()==F->GetTeam() || FVector::Dist(It->GetActorLocation(),F->GetActorLocation())>950)continue;
                Opponent=*It;break;
            }
            if(!Opponent.IsValid())return;
            LocalOriginal=F;AtSetupDeaths=PS->Deaths;AtSetupKills=PS->Kills;Setup=true;SetupAt=Now;OriginalHitTime=F->GetLocalHitTime();
            UE_LOG(LogTempleDuel,Display,TEXT("TQD|setup|%s|%.2f|%u|%d"),*DuelRole,Now,F->GetTeam(),F->GetMagazineAmmo());
        }
        if(DuelRole==TEXT("shooter"))
        {
            auto* Other=Opponent.Get();
            if(F && F->IsAlive() && Other && Other->IsAlive() && PS->Kills==AtSetupKills)
            {
                FVector Origin;FRotator Eye;F->GetActorEyesViewPoint(Origin,Eye);
                FVector Target=Other->GetActorLocation()+FVector(0,0,19.f);
                if(FirstBurst && !Firing)Target=Other->GetPawnViewLocation()+FVector(0,0,1);
                if(SecondBurst)Target=Other->GetPawnViewLocation()+FVector(0,0,1);
                const FRotator OnTarget=(Target-Origin).Rotation();
                const bool bFaceAway=bCheckFlick && !FirstBurst && Now<=SetupAt+1.3f;
                PC->SetControlRotation(bFaceAway?OnTarget+FRotator(0,85,0):OnTarget);F->SetAiming(true);
                if(!FirstBurst && Now>SetupAt+1.3f)
                {
                    F->SetTriggerHeld(true);Firing=true;FirstBurst=true;ReleaseAt=Now+.21f;
                    if(bCheckFlick){F->SetTriggerHeld(false);Firing=false;ReleaseAt=Now+.8f;}
                }
                if(bCheckFlick && FirstBurst && !bRecordedFlick && Now>=ReleaseAt)
                {
                    bRecordedFlick=true;
                    UE_LOG(LogTempleDuel,Display,TEXT("TQD|turn_and_tap|shooter|%.1f|%d|%.1f"),Other->GetHealth(),F->GetMagazineAmmo(),PS->GetPingInMilliseconds());
                }
                if(Firing && !SecondBurst && Now>=ReleaseAt){F->SetTriggerHeld(false);Firing=false;}
                if(FirstBurst && !Firing && Now>=ReleaseAt+.68f && !SecondBurst){F->SetTriggerHeld(true);Firing=true;SecondBurst=true;}
                FirstContact|=F->GetLocalHitTime()>OriginalHitTime;
                if(SecondBurst && (Now-SetupAt>5.f) && Other->IsAlive())
                    PC->SetControlRotation((Other->GetActorLocation()+FVector(0,0,19.f)-Origin).Rotation());
            }
            if(F && PS->Kills>AtSetupKills && !EndAt)
            {
                F->SetTriggerHeld(false);F->SetAiming(false);EndAt=Now+4.6f;
                UE_LOG(LogTempleDuel,Display,TEXT("TQD|frag|shooter|%d|%d|%d|%d|%.2f"),PS->Kills-AtSetupKills,F->GetMagazineAmmo(),F->GetLocalHitWasKill()?1:0,FirstContact?1:0,Now);
            }
        }
        else
        {
            if(F==LocalOriginal.Get() && F)
            {
                const float HP=F->GetHealth();LowestHP=FMath::Min(HP,LowestHP);
                if(HP<VictimPrevious){UE_LOG(LogTempleDuel,Display,TEXT("TQD|hit|target|%.1f|%.1f|%.2f"),VictimPrevious,HP,Now);VictimPrevious=HP;}
                if(!F->IsAlive()){DeadSeen=true;}
            }
            if(PS->Deaths>AtSetupDeaths && F && F!=LocalOriginal.Get() && F->IsAlive() && !EndAt)
            {
                EndAt=Now+1.f;
                UE_LOG(LogTempleDuel,Display,TEXT("TQD|respawn|target|%.1f|%.1f|%d|%.2f"),LowestHP,F->GetHealth(),PS->Deaths-AtSetupDeaths,Now);
            }
        }
    }
    void Tick(UWorld* W)
    {
        auto* G=W->GetGameState<ATempleGameState>();if(!G||Finished)return;
        float Now=G->GetServerWorldTimeSeconds();
        if(DuelRole==TEXT("server"))Server(W,G,Now);else Client(W,G,Now);
        if(EndAt>0 && Now>=EndAt){Finished=true;UE_LOG(LogTempleDuel,Display,TEXT("TQD|done|%s"),*DuelRole);FPlatformMisc::RequestExit(false);}
    }
};
TUniquePtr<FControlledEncounter> Probe;
}
void StartTempleDuel()
{
    if(!FParse::Value(FCommandLine::Get(),TEXT("TempleDuel="),DuelRole)||(DuelRole!=TEXT("server")&&DuelRole!=TEXT("shooter")&&DuelRole!=TEXT("target")))return;
    DuelHandle=FWorldDelegates::OnWorldPostActorTick.AddLambda([](UWorld* World,ELevelTick,float){
        if(!World||!World->IsGameWorld()||!World->HasBegunPlay()||!World->GetMapName().Contains(TEXT("L_CanopyDeathmatch")))return;
        if(!Probe)Probe=MakeUnique<FControlledEncounter>();Probe->Tick(World);
    });
}
void StopTempleDuel(){if(DuelHandle.IsValid())FWorldDelegates::OnWorldPostActorTick.Remove(DuelHandle);Probe.Reset();}
#endif
