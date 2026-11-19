#if !UE_BUILD_SHIPPING
#include "TempleFighter.h"
#include "AIController.h"
#include "Algo/Reverse.h"
#include "Components/CapsuleComponent.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/PlayerStart.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "HAL/PlatformMisc.h"
#include "NavigationData.h"
#include "NavigationPath.h"
#include "NavigationSystem.h"
#include "Navigation/PathFollowingComponent.h"
#include "Misc/CommandLine.h"

namespace
{
struct FTravelRoute { FString Name; TArray<FVector> Metres; };
struct FTraversalReview
{
    TArray<FTravelRoute> Routes;
    TWeakObjectPtr<ATempleFighter> Ranger;
    TWeakObjectPtr<AAIController> Pilot;
    int32 RouteIndex=0, Leg=1, NavPoints=0, Samples=0, Falling=0, Supported=0;
    float Born=0, Started=0, LastProgress=0, Walked=0, PathLength=0, MinFeet=0, MaxFeet=0;
    FVector Goal=FVector::ZeroVector, Previous=FVector::ZeroVector, ProgressMark=FVector::ZeroVector;
    bool bActive=false,bQuayThreshold=false;
    int32 ThresholdFrames=0;
    float PeakSpeed=0.f;
    void AddPair(const TCHAR* Name,TArray<FVector> P)
    {
        Routes.Add({FString(Name)+TEXT("_Out"),P});
        Algo::Reverse(P);
        Routes.Add({FString(Name)+TEXT("_Back"),P});
    }
    FTraversalReview()
    {
        bQuayThreshold=FParse::Param(FCommandLine::Get(),TEXT("TempleQuayThresholdReview"));
        if(bQuayThreshold)
        {
            const TArray<TPair<FVector,FVector>> Crossings={
                {FVector(18.30,-9.1,3.6),FVector(14.65,-9.1,4.0)},{FVector(18.35,-15.55,3.6),FVector(14.65,-16.65,4.0)},
                {FVector(19.0,-24.2,4.0),FVector(13.7,-22.8,4.0)},{FVector(18.6,-7.40,3.6),FVector(13.8,-7.65,4.0)}};
            for(int32 I=0;I<Crossings.Num();++I)
            {
                for(const TCHAR* Pace : {TEXT("Walk"),TEXT("Sprint")})
                {
                    const FString Name=FString::Printf(TEXT("FootProbe%s%02d"),Pace,I);
                    AddPair(*Name,{Crossings[I].Key,Crossings[I].Value});
                }
            }
            AddPair(TEXT("FinchNavigation"),{Crossings[0].Key,Crossings[0].Value});
            AddPair(TEXT("FinchAngledNavigation"),{Crossings[1].Key,Crossings[1].Value});
            AddPair(TEXT("FootProbeRestAtFinch"),{{16.32,-9.10,3.60},{14.40,-9.10,4}});
            return;
        }
        AddPair(TEXT("HeronEdge"),{{4.22,39.70,1.90},{9.9,39.5,4.6}});
        AddPair(TEXT("FordNorth"),{{3.5,40.25,1.5},{9.9,39.95,4.6}});
        AddPair(TEXT("FordSouth"),{{3.5,38.85,1.3},{9.9,39.05,4.6}});
        AddPair(TEXT("FordOuterNorth"),{{2.8,41.05,0.9},{9.9,41.05,4.7}});
        AddPair(TEXT("FordOuterSouth"),{{2.8,38.2,0.9},{9.9,38.2,4.6}});
        AddPair(TEXT("FordMargin"),{{3.0,39.65,0.85},{9.9,39.65,4.6}});
        AddPair(TEXT("FordCentre"),{{1.0,39.65,0},{9.9,39.65,4.6}});
        AddPair(TEXT("FootProbe"),{{1.0,39.65,0},{9.9,39.65,4.6}});
        AddPair(TEXT("FootProbeHeron"),{{4.22,39.70,1.9},{9.9,39.5,4.6}});
        AddPair(TEXT("FootProbeMidbank"),{{5.5,39.65,2.9},{9.9,39.65,4.6}});
        AddPair(TEXT("TempleFlights"),{{12,4,4.1},{15.7,0,4},{31,0,12.3},{49,0,20.1},{66.8,0,28}});
        AddPair(TEXT("Causeway"),{{-83,12,6},{-63,20,4.9},{-54,16,4.1},{-34,18,4},{-7,21.7,4.1},{11.6,26.8,4.1}});
        AddPair(TEXT("Gallery"),{{-83,12,6},{-64,40,5.3},{-47,52,5.4},{-30.46,49.84,5.3},{-12,53,5.3},{3,49.5,5.1},{11,39,4.5},{11.6,26.8,4.1}});
        AddPair(TEXT("Cloister"),{{-83,12,6},{-88,-10,6.7},{-74,-34,6.8},{-54.33,-47.67,6.3},{-14,-55,7},{10,-51,8.1},{13,-36,4.1},{12,-23,4.1},{12,4,4.1}});
    }
    void FinishRoute(const TCHAR* Status)
    {
        UE_LOG(LogTemp,Display,TEXT("TPath|route|%s|%s|%d|%d"),*Routes[RouteIndex].Name,Status,Leg-1,Routes[RouteIndex].Metres.Num()-1);
        if (Pilot.IsValid()) { Pilot->StopMovement(); Pilot->UnPossess(); Pilot->Destroy(); }
        if (Ranger.IsValid()) Ranger->Destroy();
        Pilot.Reset(); Ranger.Reset();
        ++RouteIndex; Leg=1; bActive=false;
    }
    bool IsDirect() const { return Routes[RouteIndex].Name.StartsWith(TEXT("FootProbe")); }
    void UsePlacedHome(UWorld* World)
    {
        for (TActorIterator<APlayerStart> It(World);It;++It)
        {
            if (It->PlayerStartTag!=TEXT("Blue") || It->GetActorNameOrLabel()!=TEXT("Blue Arrival 1")) continue;
            const FVector Home=(It->GetActorLocation()-FVector(0,0,104))/100.;
            for (auto& Route:Routes)
            {
                const bool bOut=Route.Name.EndsWith(TEXT("_Out"));
                if (Route.Name.StartsWith(TEXT("Causeway")) || Route.Name.StartsWith(TEXT("Gallery")))
                    Route.Metres[bOut?Route.Metres.Num()-1:0]=Home;
                else if (Route.Name.StartsWith(TEXT("Cloister")))
                {
                    if (bOut) Route.Metres.Add(Home);
                    else Route.Metres.Insert(Home,0);
                }
            }
            break;
        }
    }
    bool Report(const TCHAR* Reason,const FVector& Position) const
    {
        UE_LOG(LogTemp,Display,TEXT("TProbe|%s|%s|%s"),*Routes[RouteIndex].Name,Reason,*Position.ToCompactString());
        return false;
    }
    bool Project(UNavigationSystemV1* Nav,const FVector& P,FVector& Out) const
    {
        FNavLocation N;
        if (!Nav->ProjectPointToNavigation(P*100.,N,FVector(85,85,250))) return false;
        Out=N.Location;
        return true;
    }
    void SurveyBank(UWorld* World,UNavigationSystemV1* Nav) const
    {
        const FCollisionQueryParams Query(SCENE_QUERY_STAT(TempleFordSurvey),false);
        for (float Y : {38.20f,38.85f,39.65f,40.25f,41.05f})
        {
            const FVector Top(990,Y*100,460);
            FNavLocation End;
            if (!Nav->ProjectPointToNavigation(Top,End,FVector(80,80,150))) continue;
            for (int32 I=0;I<=20;++I)
            {
                const FVector P(50.f*I,Y*100,0);
                FHitResult Support;
                if (!World->LineTraceSingleByChannel(Support,P+FVector(0,0,700),P-FVector(0,0,500),ECC_Pawn,Query)) continue;
                FNavLocation N;
                const bool bProjected=Nav->ProjectPointToNavigation(Support.ImpactPoint,N,FVector(58,58,140));
                auto* Path=bProjected?UNavigationSystemV1::FindPathToLocationSynchronously(World,N.Location,End.Location):nullptr;
                const auto* Owner=Support.GetActor();
                UE_LOG(LogTemp,Display,TEXT("TFord|%.2f|%.2f|%.2f|%.2f|%s|%s|%s|%d|%d|%.1f"),
                    P.X/100,Y,Support.ImpactPoint.Z/100,Support.ImpactNormal.Z,
                    Owner?*Owner->GetActorNameOrLabel():TEXT("none"),*GetNameSafe(Support.GetComponent()),
                    bProjected?*N.Location.ToCompactString():TEXT("none"),Path && Path->IsValid(),Path && Path->IsPartial(),Path?Path->GetPathLength():0);
            }
        }
    }
    bool Place(UWorld* World,UNavigationSystemV1* Nav)
    {
        if (!RouteIndex && FParse::Param(FCommandLine::Get(),TEXT("TempleRangerWithBot"))) UsePlacedHome(World);
        const auto& Route=Routes[RouteIndex];
        if (!RouteIndex) SurveyBank(World,Nav);
        const FVector Start=Route.Metres[0]*100.;
        UClass* RangerClass=LoadClass<ATempleFighter>(nullptr,TEXT("/Game/TempleTDM/Rules/BP_CanopyRanger.BP_CanopyRanger_C"));
        const auto* Default=RangerClass?Cast<ATempleFighter>(RangerClass->GetDefaultObject()):nullptr;
        if (!Default) return Report(TEXT("no_ranger_class"),Start);
        const auto* Capsule=Default->GetCapsuleComponent();
        const float Half=Capsule->GetScaledCapsuleHalfHeight();
        const auto Shape=FCollisionShape::MakeCapsule(Capsule->GetScaledCapsuleRadius(),Half);
        FHitResult Floor;
        FCollisionQueryParams Query(SCENE_QUERY_STAT(TempleRouteFloor),false);
        if (!World->SweepSingleByChannel(Floor,Start+FVector(0,0,Half+160),Start+FVector(0,0,Half-180),FQuat::Identity,ECC_Pawn,Shape,Query))
            return Report(TEXT("no_capsule_floor"),Start);
        FActorSpawnParameters Spawn;
        Spawn.SpawnCollisionHandlingOverride=ESpawnActorCollisionHandlingMethod::DontSpawnIfColliding;
        const FVector Centre=Floor.Location+FVector(0,0,3);
        Ranger=World->SpawnActor<ATempleFighter>(RangerClass,Centre,(Route.Metres[1]-Route.Metres[0]).GetSafeNormal2D().Rotation(),Spawn);
        if (!Ranger.IsValid()) return Report(TEXT("overlapping_capsule_at_start"),Centre);
        if (AController* Existing=Ranger->GetController()) { Existing->UnPossess(); Existing->Destroy(); }
        static const bool bUseArenaBot=FParse::Param(FCommandLine::Get(),TEXT("TempleRangerWithBot"));
        UClass* PilotClass=bUseArenaBot?
            LoadClass<AAIController>(nullptr,TEXT("/Game/TempleTDM/Rules/BP_CanopyBot.BP_CanopyBot_C")):
            AAIController::StaticClass();
        Pilot=PilotClass?World->SpawnActor<AAIController>(PilotClass):nullptr;
        if (!Pilot.IsValid()) return false;
        Pilot->Possess(Ranger.Get());
        Ranger->SetTeam(0);
        if(bQuayThreshold && Route.Name.Contains(TEXT("Sprint")))
        {
            bool bPressed=true;
            Ranger->ProcessEvent(Ranger->FindFunctionChecked(TEXT("ServerSetSprinting")),&bPressed);
        }
        Born=World->GetTimeSeconds();
        UE_LOG(LogTemp,Display,TEXT("TPath|start|%s|%s|%s|%s|%s|%.1f|%.1f"),
            *Route.Name,*Ranger->GetClass()->GetName(),*Start.ToCompactString(),*Ranger->GetActorLocation().ToCompactString(),
            *GetNameSafe(Floor.GetActor()),Ranger->GetCapsuleComponent()->GetScaledCapsuleRadius(),Half);
        return true;
    }
    bool BeginLeg(UWorld* World,UNavigationSystemV1* Nav)
    {
        const auto& Route=Routes[RouteIndex];
        const FVector Desired=Route.Metres[Leg]*100.;
        Previous=Ranger->GetActorLocation(); ProgressMark=Previous;
        FHitResult Support;
        FCollisionQueryParams Query(SCENE_QUERY_STAT(TempleRouteDestination),false,Ranger.Get());
        if (!World->LineTraceSingleByChannel(Support,Desired+FVector(0,0,145),Desired-FVector(0,0,165),ECC_Pawn,Query))
            return Report(TEXT("goal_has_no_pawn_floor"),Desired);
        Goal=Support.ImpactPoint;
        NavPoints=0; PathLength=FVector::Dist2D(Previous,Goal);
        if (!IsDirect())
        {
            FVector NavGoal;
            if (!Project(Nav,Route.Metres[Leg],NavGoal)) return Report(TEXT("goal_nav_projection_failed"),Goal);
            FAIMoveRequest Request(NavGoal);
            Request.SetAcceptanceRadius(19.f);
            Request.SetReachTestIncludesAgentRadius(false);
            Request.SetReachTestIncludesGoalRadius(false);
            Request.SetAllowPartialPath(false);
            Request.SetProjectGoalLocation(false);
            Request.SetUsePathfinding(true);
            FNavPathSharedPtr NativePath;
            auto Result=Pilot->MoveTo(Request,&NativePath);
            if (Result.Code==EPathFollowingRequestResult::Failed)
            {
                UE_LOG(LogTemp,Display,TEXT("TProbe|%s|move_to_failed|fromFeet=%s|goal=%s|navGoal=%s|partial=%d"),
                    *Route.Name,*Ranger->GetNavAgentLocation().ToCompactString(),*Goal.ToCompactString(),*NavGoal.ToCompactString(),
                    NativePath.IsValid() && NativePath->IsPartial());
                return false;
            }
            if (NativePath.IsValid())
            {
                NavPoints=NativePath->GetPathPoints().Num();
                PathLength=NativePath->GetLength();
            }
            UE_LOG(LogTemp,Display,TEXT("TProbe|%s|native_goal|%s|physical_goal|%s"),*Route.Name,*NavGoal.ToCompactString(),*Goal.ToCompactString());
            Goal.X=NavGoal.X; Goal.Y=NavGoal.Y;
        }
        Started=LastProgress=World->GetTimeSeconds();
        MinFeet=MaxFeet=Previous.Z-Ranger->GetCapsuleComponent()->GetScaledCapsuleHalfHeight();
        Walked=PeakSpeed=0; Samples=Falling=Supported=ThresholdFrames=0; bActive=true;
        return true;
    }
    void FinishLeg(UWorld* World,const TCHAR* Status)
    {
        auto* Move=Ranger->GetCharacterMovement();
        const FVector Current=Ranger->GetActorLocation();
        if(bQuayThreshold)UE_LOG(LogTemp,Display,TEXT("TQuayThreshold|%s|%s|%.1f|%.1f|%d|%d|%d"),
            *Routes[RouteIndex].Name,Status,PeakSpeed,Move->MaxWalkSpeed,ThresholdFrames,Supported,Falling);
        FCollisionQueryParams Query(SCENE_QUERY_STAT(TempleRouteBlock),false,Ranger.Get());
        FHitResult Block;
        const FVector Direction=(Goal-Current).GetSafeNormal2D();
        const auto* Capsule=Ranger->GetCapsuleComponent();
        World->SweepSingleByChannel(Block,Current+FVector(0,0,4),Current+FVector(0,0,4)+Direction*105.,FQuat::Identity,
            ECC_Pawn,FCollisionShape::MakeCapsule(Capsule->GetScaledCapsuleRadius()-.5f,Capsule->GetScaledCapsuleHalfHeight()-4),Query);
        UE_LOG(LogTemp,Display,TEXT("TPath|leg|%s|%d|%s|%.2f|%.1f|%.1f|%d|%d|%d|%d|%.1f|%.1f|%s|%s|%s|%s|%s|%s"),
            *Routes[RouteIndex].Name,Leg,Status,World->GetTimeSeconds()-Started,Walked,PathLength,NavPoints,
            Samples,Supported,Falling,MinFeet,MaxFeet,*Current.ToCompactString(),*Goal.ToCompactString(),
            *GetNameSafe(Move->CurrentFloor.HitResult.GetActor()),*Move->CurrentFloor.HitResult.ImpactNormal.ToCompactString(),
            Block.GetActor()?*Block.GetActor()->GetActorNameOrLabel():TEXT("none"),*Block.ImpactNormal.ToCompactString());
    }
    void Tick(UWorld* World)
    {
        if (!World || !World->IsGameWorld() || World->GetNetMode()==NM_Client || !World->GetMapName().Contains(TEXT("L_CanopyDeathmatch"))) return;
        const float Now=World->GetTimeSeconds();
        if (Now<1) return;
        if (!Routes.IsValidIndex(RouteIndex)) { FPlatformMisc::RequestExit(false); return; }
        auto* Nav=FNavigationSystem::GetCurrent<UNavigationSystemV1>(World);
        if (!Nav || !Nav->GetDefaultNavDataInstance(FNavigationSystem::DontCreate)) return;
        if (!Ranger.IsValid())
        {
            if (!Place(World,Nav)) FinishRoute(TEXT("start_failed"));
            return;
        }
        if (Now-Born<.33f) return;
        if (!bActive)
        {
            if (!BeginLeg(World,Nav)) FinishRoute(TEXT("path_failed"));
            return;
        }
        auto* Move=Ranger->GetCharacterMovement();
        const FVector Here=Ranger->GetActorLocation();
        const float Feet=Here.Z-Ranger->GetCapsuleComponent()->GetScaledCapsuleHalfHeight();
        Walked+=FVector::Dist(Here,Previous); Previous=Here;
        ++Samples;
        if(bQuayThreshold)
        {
            PeakSpeed=FMath::Max(PeakSpeed,float(Ranger->GetVelocity().Size2D()));
            AActor* FloorActor=Move->CurrentFloor.HitResult.GetActor();
            if(FloorActor && FloorActor->GetActorNameOrLabel().StartsWith(TEXT("South Quay Threshold")))++ThresholdFrames;
        }
        Supported+=Move->CurrentFloor.IsWalkableFloor()?1:0;
        Falling+=Move->IsFalling()?1:0;
        MinFeet=FMath::Min(MinFeet,Feet); MaxFeet=FMath::Max(MaxFeet,Feet);
        if (FVector::DistSquared(Here,ProgressMark)>FMath::Square(18.)) { ProgressMark=Here;LastProgress=Now; }
        const bool bFord=Routes[RouteIndex].Name.StartsWith(TEXT("Ford")) || Routes[RouteIndex].Name.StartsWith(TEXT("Heron")) || IsDirect();
        const bool bAtGoal=Move->IsMovingOnGround() && Move->CurrentFloor.IsWalkableFloor() &&
            FVector::Dist2D(Here,Goal)<(bFord?29:39) && FMath::Abs(Feet-Goal.Z)<(bFord?41:73);
        if (IsDirect()) Ranger->AddMovementInput((Goal-Here).GetSafeNormal2D(),1.f);
        if (bAtGoal)
        {
            FinishLeg(World,TEXT("reached")); ++Leg;bActive=false;
            if (Leg>=Routes[RouteIndex].Metres.Num()) FinishRoute(TEXT("passed"));
            return;
        }
        const bool Stuck=Now-LastProgress>3.25f;
        if (Stuck || Now-Started>FMath::Max(9.f,PathLength/140.f+5.f) ||
            (!IsDirect() && Now-Started>.5f && Pilot->GetMoveStatus()==EPathFollowingStatus::Idle))
        {
            const TCHAR* Reason=Stuck?TEXT("stalled"):TEXT("move_ended");
            FinishLeg(World,Reason); FinishRoute(Reason);
        }
    }
};
TUniquePtr<FTraversalReview> Review;
FDelegateHandle TraversalTickHandle;
}
void StartTempleTraversalReview()
{
    if (!FParse::Param(FCommandLine::Get(),TEXT("TempleTraversalReview"))) return;
    Review=MakeUnique<FTraversalReview>();
    TraversalTickHandle=FWorldDelegates::OnWorldPostActorTick.AddLambda([](UWorld* W,ELevelTick,float){if(Review)Review->Tick(W);});
}
void StopTempleTraversalReview()
{
    if (TraversalTickHandle.IsValid()) FWorldDelegates::OnWorldPostActorTick.Remove(TraversalTickHandle);
    Review.Reset();
}
#endif
