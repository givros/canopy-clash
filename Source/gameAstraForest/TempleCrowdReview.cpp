#if !UE_BUILD_SHIPPING
#include "TempleFighter.h"
#include "TempleBotController.h"
#include "Components/CapsuleComponent.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/PlayerController.h"
#include "HAL/PlatformMisc.h"
#include "Misc/CommandLine.h"
#include "Navigation/CrowdFollowingComponent.h"
#include "Navigation/CrowdManager.h"
#include "NavigationSystem.h"

namespace
{
struct FCrowdCase { const TCHAR* Name; FVector A,B,Standing; bool bBlocker; FVector SecondStart={},SecondGoal={}; bool bConverge=false; };
struct FCrowdCheck
{
    const TArray<FCrowdCase> Cases={
        {TEXT("QuayMeeting"),{-12.2,20.8,4},{.2,21.6,4},{},false},
        {TEXT("QuayStationary"),{-12.2,20.8,4},{.2,21.6,4},{-6.3,20.65,4},true},
        {TEXT("PlazaMeeting"),{10.45,11.4,4},{10.55,18.2,4},{},false},
        {TEXT("PlazaStationary"),{10.45,11.4,4},{10.55,18.2,4},{10.5,14.6,4},true},
        {TEXT("RailMeeting"),{11.27,9.66,4},{10.45,16.3,4},{},false,{10.56,9.57,4},{11.2,4.4,4}},
        {TEXT("RailStationary"),{11.27,9.66,4},{10.45,16.3,4},{10.56,9.57,4},true},
        {TEXT("RailConvergence"),{10.56,9.57,4},{11.2,4.4,4},{},false,{11.27,9.66,4},{10.45,16.3,4},true}
    };
    TWeakObjectPtr<ATempleFighter> Pawns[2];
    TWeakObjectPtr<AController> Controllers[2];
    FVector Starts[2],Goals[2],Previous[2];
    float Travel[2]={}, StartTime=0,MinSeparation=0;
    int32 Case=0,MovingFrames=0;
    bool bRequested=false,Reached[2]={},bReleased=false,bResumed=false;
    double LargestGap=0;
    void Finish(UWorld* W,bool Passed)
    {
        const FVector End0=Pawns[0].IsValid()?Pawns[0]->GetActorLocation():FVector::ZeroVector;
        const FVector End1=Pawns[1].IsValid()?Pawns[1]->GetActorLocation():FVector::ZeroVector;
        UE_LOG(LogTemp,Display,TEXT("TCrowd|%s|%s|%.2f|%.1f|%.1f|%.1f|%.1f|%d|%s|%s"),
            Cases[Case].Name,Passed?TEXT("passed"):TEXT("failed"),W->GetTimeSeconds()-StartTime,Travel[0],Travel[1],MinSeparation,
            FVector::Dist2D(End1,Starts[1]),MovingFrames,*End0.ToCompactString(),*End1.ToCompactString());
        for (int32 I=0;I<2;++I)
        {
            if (Controllers[I].IsValid()){Controllers[I]->UnPossess();Controllers[I]->Destroy();}
            if (Pawns[I].IsValid())Pawns[I]->Destroy();
            Controllers[I].Reset();Pawns[I].Reset();
            Travel[I]=0;Reached[I]=false;
        }
        ++Case;bRequested=false;bReleased=false;bResumed=false;LargestGap=0;
    }
    bool Create(UWorld* W)
    {
        const auto& C=Cases[Case];
        auto* Nav=FNavigationSystem::GetCurrent<UNavigationSystemV1>(W);
        UClass* Ranger=LoadClass<ATempleFighter>(nullptr,TEXT("/Game/TempleTDM/Rules/BP_CanopyRanger.BP_CanopyRanger_C"));
        UClass* Bot=LoadClass<ATempleBotController>(nullptr,TEXT("/Game/TempleTDM/Rules/BP_CanopyBot.BP_CanopyBot_C"));
        if (!Ranger || !Bot || !Nav) return false;
        StartTime=W->GetTimeSeconds();MinSeparation=MAX_flt;MovingFrames=0;
        for(int32 I=0;I<2;++I)
        {
            const FVector OtherStart=C.bBlocker?C.Standing:(C.SecondStart.IsNearlyZero()?C.B:C.SecondStart);
            const FVector Start=(I?OtherStart:C.A)*100.;
            Starts[I]=Start;
            FHitResult Floor;
            if(!W->SweepSingleByChannel(Floor,Start+FVector(0,0,196),Start,FQuat::Identity,ECC_Pawn,FCollisionShape::MakeCapsule(34,96)))return false;
            const FVector Centre=Floor.Location+FVector(0,0,3);
            auto* F=W->SpawnActor<ATempleFighter>(Ranger,Centre,FRotator::ZeroRotator);
            if(!F)return false;
            Pawns[I]=F;
            if(auto* Old=F->GetController()){Old->UnPossess();Old->Destroy();}
            auto* Pilot=(I && C.bBlocker)?W->SpawnActor<AController>(APlayerController::StaticClass()):W->SpawnActor<AController>(Bot);
            if(!Pilot)return false;
            Controllers[I]=Pilot;Pilot->Possess(F);F->SetTeam(1);
            FNavLocation Projected;
            const FVector End=I?(C.SecondGoal.IsNearlyZero()?C.A:C.SecondGoal):C.B;
            if(!Nav->ProjectPointToNavigation(End*100.,Projected,FVector(70,70,160)))return false;
            Goals[I]=Projected.Location;
            Previous[I]=Starts[I]=F->GetActorLocation();
        }
        return true;
    }
    void Tick(UWorld* W)
    {
        if(!W || !W->IsGameWorld() || W->GetNetMode()!=NM_DedicatedServer || W->GetTimeSeconds()<1) return;
        if (!Cases.IsValidIndex(Case)) {FPlatformMisc::RequestExit(false);return;}
        if(!Pawns[0].IsValid()){if(!Create(W))Finish(W,false);return;}
        const auto& C=Cases[Case];
        const float Elapsed=W->GetTimeSeconds()-StartTime;
        if(Elapsed<.4f)return;
        if(!bRequested)
        {
            for(int32 I=0;I<(C.bBlocker?1:2);++I)
            {
                auto* AI=CastChecked<ATempleBotController>(Controllers[I].Get());
                if(C.bConverge && I==0)continue;
                FVector Destination=C.bConverge?Starts[0]-FVector(0,0,96):Goals[I];
                if(AI->MoveToLocation(Destination,C.bConverge?4.f:26.f,false,true,false,true,nullptr,false)==EPathFollowingRequestResult::Failed)
                    {Finish(W,false);return;}
            }
            auto* Profile=Cast<UCrowdFollowingComponent>(CastChecked<ATempleBotController>(Controllers[0].Get())->GetPathFollowingComponent());
            auto* Crowd=UCrowdManager::GetCurrent(W);
            UE_LOG(LogTemp,Display,TEXT("TCrowdComponent|%s|%s|registered=%d|player_obstacle=%d"),C.Name,*GetNameSafe(Profile),
                Crowd && Profile && Crowd->IsAgentValid(Profile),C.bBlocker && Crowd && Crowd->IsAgentValid(Pawns[1].Get()));
            bRequested=true;
        }
        if(C.bConverge)
        {
            if(!bReleased)
            {
                LargestGap=FMath::Max(LargestGap,FVector::Dist2D(Pawns[0]->GetActorLocation(),Pawns[1]->GetActorLocation()));
                if(Elapsed>=3.7f)
                {
                    UE_LOG(LogTemp,Display,TEXT("TCrowdConvergence|before_release|%.1f|%.1f|%.1f"),LargestGap,Travel[1],
                        FVector::Dist2D(Starts[0],Pawns[0]->GetActorLocation()));
                    CastChecked<ATempleBotController>(Controllers[0].Get())->MoveToLocation(Goals[0],26,false);
                    bReleased=true;
                }
            }
            else if(!bResumed && FVector::Dist2D(Pawns[1]->GetActorLocation(),Starts[0])<31)
            {
                UE_LOG(LogTemp,Display,TEXT("TCrowdConvergence|original_goal_reached|%.2f"),Elapsed);
                bResumed=true;
                CastChecked<ATempleBotController>(Controllers[1].Get())->MoveToLocation(Goals[1],26,false);
            }
        }
        for(int32 I=0;I<2;++I)
        {
            auto* F=Pawns[I].Get(); const FVector P=F->GetActorLocation();
            Travel[I]+=FVector::Dist2D(Previous[I],P);Previous[I]=P;
            Reached[I]|=FVector::Dist2D(P,Goals[I])<45 && F->GetCharacterMovement()->IsMovingOnGround();
        }
        ++MovingFrames;MinSeparation=FMath::Min(MinSeparation,float(FVector::Dist2D(Previous[0],Previous[1])));
        if(Reached[0] && (C.bBlocker?FVector::Dist2D(Previous[1],Starts[1])<3:Reached[1])){Finish(W,true);return;}
        if(Elapsed>15)Finish(W,false);
    }
};
FDelegateHandle CrowdCheckHandle;
TUniquePtr<FCrowdCheck> CrowdCheck;
}
void StartTempleCrowdReview()
{
    if(!FParse::Param(FCommandLine::Get(),TEXT("TempleCrowdReview")))return;
    CrowdCheck=MakeUnique<FCrowdCheck>();
    CrowdCheckHandle=FWorldDelegates::OnWorldPostActorTick.AddLambda([](UWorld* W,ELevelTick,float){CrowdCheck->Tick(W);});
}
void StopTempleCrowdReview()
{
    if(CrowdCheckHandle.IsValid())FWorldDelegates::OnWorldPostActorTick.Remove(CrowdCheckHandle);
    CrowdCheck.Reset();
}
#endif
