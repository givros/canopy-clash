#include "TempleBotController.h"
#include "TempleDeploymentNavigation.h"
#include "TempleFighter.h"
#include "TempleMatch.h"
#include "EngineUtils.h"
#include "Components/CapsuleComponent.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "NavigationSystem.h"
#include "Navigation/PathFollowingComponent.h"
#include "Navigation/CrowdFollowingComponent.h"

namespace
{
bool ProjectForRoute(const ATempleBotController& Bot, const FVector& Position, const FVector& Extent, FNavLocation& Result)
{
    const UNavigationSystemV1* Navigation = FNavigationSystem::GetCurrent<UNavigationSystemV1>(Bot.GetWorld());
    if (!Navigation || !Bot.GetPawn()) return false;
    const ANavigationData* Data = Navigation->GetNavDataForProps(Bot.GetNavAgentPropertiesRef(), Bot.GetPawn()->GetActorLocation());
    if (!Data) return false;
    const auto Filter = UNavigationQueryFilter::GetQueryFilter(*Data, &Bot, Bot.GetDefaultNavigationFilterClass());
    return Navigation->ProjectPointToNavigation(Position, Result, Extent, Data, Filter);
}
}

ATempleBotController::ATempleBotController(const FObjectInitializer& ObjectInitializer)
    : Super(ObjectInitializer.SetDefaultSubobjectClass<UCrowdFollowingComponent>(TEXT("PathFollowingComponent")))
{
    bWantsPlayerState=true;
    PrimaryActorTick.bCanEverTick=true;
    bAllowStrafe=true;
    auto* Crowd=CastChecked<UCrowdFollowingComponent>(GetPathFollowingComponent());
    Crowd->SetCrowdAvoidanceQuality(ECrowdAvoidanceQuality::Good,false);
    Crowd->SetCrowdSeparation(true,false);
    Crowd->SetCrowdPathOffset(true,false);
    Crowd->SetCrowdRotateToVelocity(false);
}

void ATempleBotController::OnPossess(APawn* NewPawn)
{
    Super::OnPossess(NewPawn);
    if (const auto* Side = GetPlayerState<ATemplePlayerState>(); Side && Side->Team < 2)
        DefaultNavigationFilterClass = Side->Team == 0 ? UTempleRedRouteFilter::StaticClass() : UTempleBlueRouteFilter::StaticClass();
    PatrolLane=PatrolStation=INDEX_NONE;bFollowingPatrol=false;
    Target.Reset(); bTracking=false; bSearching=false; bBurst=false; bHasMoveGoal=false; bWasActive=false;
    SeenTime=-1000.f; LastDamageNotice=-1000.f; YieldUntil=0.f;ContinuousMoveSince=-1.f;
    Personality=FMath::FRandRange(0.f,2.f*PI);
    AimWobble=FMath::FRandRange(.8f,1.35f);
    const float Now=GetWorld()->GetTimeSeconds();
    NextSense=Now+FMath::FRandRange(.05f,.28f);
    NextReposition=Now; NextProgressCheck=Now+1.65f;
    LastProgressLocation=NewPawn->GetActorLocation();
}

void ATempleBotController::OnUnPossess()
{
    if (ATempleFighter* Self=Cast<ATempleFighter>(GetPawn())) Self->SetTriggerHeld(false);
    Target.Reset(); bTracking=false; bBurst=false; bHasMoveGoal=false; bSearching=false;
    Super::OnUnPossess();
}

bool ATempleBotController::VisibleTarget(ATempleFighter* Self,ATempleFighter* Other,const FVector& Eye,
    const FVector& Forward,const ATempleMatchMode* Mode,FVector& OutSeen) const
{
    if (Other==Self || !Other->IsAlive() || Other->GetTeam()>1 || Other->GetTeam()==Self->GetTeam() || Other->IsSpawnProtected()) return false;
    const FVector Centre=Other->GetActorLocation();
    if (Mode->IsEnemySafeZone(Self->GetTeam(),Centre) && !Other->HasRecentServerShot(GetWorld()->GetTimeSeconds())) return false;
    const FVector Delta=Centre-Eye;
    const float Distance=Delta.Size();
    if (Distance>SightDistance || Distance<1.f) return false;
    const float Dot=FVector::DotProduct(Forward,Delta/Distance);
    if (Distance>370.f && Dot<FMath::Cos(FMath::DegreesToRadians(PeripheralHalfAngle))) return false;
    FCollisionQueryParams Query(SCENE_QUERY_STAT(TempleSight),false,Self);
    for (const float Offset : {27.f,Other->BaseEyeHeight-3.f})
    {
        const FVector Probe=Centre+FVector(0,0,Offset);
        FHitResult Hit;
        if (!GetWorld()->LineTraceSingleByChannel(Hit,Eye,Probe,ECC_Visibility,Query) || Hit.GetActor()==Other)
        { OutSeen=Probe; return true; }
    }
    return false;
}

bool ATempleBotController::MoveToGround(const FVector& Destination,float Acceptance)
{
    if(YieldUntil>0.f)return true;
    FNavLocation Ground;
    if (!ProjectForRoute(*this,Destination,FVector(195,195,410),Ground)) return false;
    if (bHasMoveGoal && FVector::DistSquared2D(Ground.Location,MoveGoal)<FMath::Square(75.f) &&
        GetMoveStatus()==EPathFollowingStatus::Moving) return true;
    const EPathFollowingRequestResult::Type Result=MoveToLocation(Ground.Location,Acceptance,true,true,false,true,DefaultNavigationFilterClass,false);
    if (Result==EPathFollowingRequestResult::Failed) return false;
    MoveGoal=Ground.Location; bHasMoveGoal=Result==EPathFollowingRequestResult::RequestSuccessful;
    return true;
}

bool ATempleBotController::TryYieldToTeammate(ATempleFighter* Self,ATempleMatchMode* Mode,float Now)
{
#if !UE_BUILD_SHIPPING
    static const bool bControl=FParse::Param(FCommandLine::Get(),TEXT("TempleCrowdYieldControl"));
    if(bControl)return false;
#endif
    const FVector Here=Self->GetActorLocation();
    const UCapsuleComponent* Capsule=Self->GetCapsuleComponent();
    const float Radius=Capsule->GetScaledCapsuleRadius();
    const float HalfHeight=Capsule->GetScaledCapsuleHalfHeight();
    const auto* MyState=GetPlayerState<APlayerState>();
    ATempleFighter* Neighbor=nullptr;
    double ClosestSquared=FMath::Square(2.f*Radius+32.f);
    for(TActorIterator<ATempleFighter> It(GetWorld());It;++It)
    {
        auto* Other=*It;
        if(Other==Self || !Other->IsAlive() || Other->GetTeam()!=Self->GetTeam() || !Other->GetController())continue;
        const FVector Delta=Here-Other->GetActorLocation();
        const double DistanceSquared=Delta.SizeSquared2D();
        if(FMath::Abs(Delta.Z)>HalfHeight || DistanceSquared>=ClosestSquared)continue;
        const auto* OtherState=Other->GetPlayerState();
        const bool HigherPriority=MyState && OtherState && MyState->GetPlayerId()!=OtherState->GetPlayerId()
            ? OtherState->GetPlayerId()<MyState->GetPlayerId() : Other->GetUniqueID()<Self->GetUniqueID();
        if(!Other->IsPlayerControlled() && !HigherPriority)continue;
        Neighbor=Other;
        ClosestSquared=DistanceSquared;
    }
    if(!Neighbor)return false;
    const FVector Feet=Self->GetCharacterMovement()->GetActorFeetLocation();
    FNavLocation Origin;
    if(!ProjectForRoute(*this,Feet,FVector(55,55,100),Origin))return false;
    const FVector Away=(Here-Neighbor->GetActorLocation()).GetSafeNormal2D();
    const FVector Side=FVector::CrossProduct(FVector::UpVector,Away);
    const FVector Back=(Here-GetImmediateMoveDestination()).GetSafeNormal2D();
    const FCollisionShape Shape=FCollisionShape::MakeCapsule(Radius-1.f,HalfHeight-4.f);
    FCollisionQueryParams Sweep(SCENE_QUERY_STAT(TempleYieldSweep),false,Self);
    const FVector Resume=GetPathFollowingComponent()->GetPathDestination();
    const float Acceptance=GetPathFollowingComponent()->GetAcceptanceRadius();
    for(const FVector& Direction : {Side,-Side,Away,Back,(Side-Away).GetSafeNormal2D(),(-Side-Away).GetSafeNormal2D()})
    {
        const FVector Candidate=Feet+Direction*128.f;
        FNavLocation Ground;
        if(!ProjectForRoute(*this,Candidate,FVector(32,32,95),Ground) ||
           FVector::DistSquared2D(Ground.Location,Candidate)>FMath::Square(33.f) ||
           FVector::DistSquared2D(Ground.Location,Neighbor->GetActorLocation())<FMath::Square(2.f*Radius+34.f) ||
           (Mode && Mode->IsEnemySafeZone(Self->GetTeam(),Ground.Location)))continue;
        FVector Wall;
        if(UNavigationSystemV1::NavigationRaycast(GetWorld(),Origin.Location,Ground.Location,Wall,DefaultNavigationFilterClass,this))continue;
        const FVector End(Ground.Location.X,Ground.Location.Y,Here.Z+Ground.Location.Z-Origin.Location.Z);
        if(GetWorld()->SweepTestByChannel(Here,End,FQuat::Identity,ECC_Pawn,Shape,Sweep))continue;
        // A stationary player will still occupy this spot when the short yield is over.
        // Accept a step only if the bot can continue past that player from its new side.
        if(Neighbor->IsPlayerControlled())
        {
            const FVector Forward=(Resume-End).GetSafeNormal2D();
            const FVector Exit=End+Forward*FMath::Min(235.,FVector::Dist2D(End,Resume));
            if(GetWorld()->SweepTestByChannel(End,Exit,FQuat::Identity,ECC_Pawn,Shape,Sweep))continue;
        }
        if(MoveToLocation(Ground.Location,16.f,false,true,false,true,DefaultNavigationFilterClass,false)!=EPathFollowingRequestResult::RequestSuccessful)continue;
        ResumeDestination=Resume;ResumeAcceptance=Acceptance;bResumeStopOnOverlap=bHasMoveGoal;YieldUntil=Now+.85f;
#if !UE_BUILD_SHIPPING
        static const bool bReview=FParse::Param(FCommandLine::Get(),TEXT("TempleCrowdReview")) || FParse::Param(FCommandLine::Get(),TEXT("TempleBalanceYieldReview"));
        if(bReview)UE_LOG(LogTemp,Display,TEXT("TCrowdYield|%s|%s|%.2f|%s|%s|%s"),*GetNameSafe(Self),*GetNameSafe(Neighbor),Now,*Here.ToCompactString(),*End.ToCompactString(),*Resume.ToCompactString());
#endif
        return true;
    }
    return false;
}

void ATempleBotController::CheckMovementProgress(ATempleFighter* Self,ATempleMatchMode* Mode,float Now)
{
    if(YieldUntil>0.f)
    {
        if(Now<YieldUntil)return;
        YieldUntil=0.f;
        if(!Mode || !Mode->IsEnemySafeZone(Self->GetTeam(),ResumeDestination))
        {
            MoveToLocation(ResumeDestination,ResumeAcceptance,bResumeStopOnOverlap,true,false,true,DefaultNavigationFilterClass,false);
        }
        LastProgressLocation=Self->GetActorLocation();NextProgressCheck=Now+1.7f;
        return;
    }
    const bool bMoving=GetMoveStatus()==EPathFollowingStatus::Moving;
    if(!bMoving)ContinuousMoveSince=-1.f;
    else if(ContinuousMoveSince<0.f)ContinuousMoveSince=Now;
    if(Now<NextProgressCheck)return;
    const bool bSlow=FVector::DistSquared2D(LastProgressLocation,Self->GetActorLocation())<FMath::Square(40.f);
    LastProgressLocation=Self->GetActorLocation();NextProgressCheck=Now+1.7f;
    if(!bSlow)return;
    if(bMoving && Now-ContinuousMoveSince>=1.45f && TryYieldToTeammate(Self,Mode,Now))return;
    if(Mode && bHasMoveGoal)
    {
        StopMovement();bHasMoveGoal=false;NextReposition=Now;bSearching=false;
    }
}

void ATempleBotController::Patrol(ATempleFighter* Self,ATempleMatchMode* Mode,float Now)
{
    if (bFollowingPatrol && bHasMoveGoal && GetMoveStatus()==EPathFollowingStatus::Moving) return;
    const FVector Here=Self->GetActorLocation();
    if(PatrolLane==INDEX_NONE)
    {
        const auto* PS=GetPlayerState<ATemplePlayerState>();
        static const int32 Rotation[]={0,0,1,2,3};
        // Keep the opening spread. Each elimination sends this fighter to a different approach.
        const int32 RouteCount=UE_ARRAY_COUNT(Rotation);
        const int32 StartingSlot=PS?FMath::Abs(PS->GetPlayerId()%RouteCount):0;
        const int32 FlankOffset=PS?2*(PS->Deaths%RouteCount):0;
        PatrolLane=Rotation[(StartingSlot+FlankOffset)%RouteCount];
    }
    FVector Waypoint;
    if(Mode->GetLaneGoal(Self->GetTeam(),PatrolLane,Here,PatrolStation,PatrolDirection,Waypoint))
    {
        const float SideOffset=95.f*FMath::Sin(Personality);
        const FVector Across=FVector::CrossProduct((Waypoint-Here).GetSafeNormal2D(),FVector::UpVector);
        if(MoveToGround(Waypoint+Across*SideOffset,75.f)){bFollowingPatrol=true;return;}
    }
    if(Now<NextReposition && bHasMoveGoal)return;
    bFollowingPatrol=false;
    for (int32 Try=0;Try<4;++Try)
    {
        FVector Goal=Mode->GetPatrolGoal(Self->GetTeam(),Here);
        Goal+=FVector(FMath::FRandRange(-155.f,155.f),FMath::FRandRange(-155.f,155.f),0);
        if (!Mode->IsEnemySafeZone(Self->GetTeam(),Goal) && MoveToGround(Goal,72.f)) break;
    }
    NextReposition=Now+FMath::FRandRange(4.2f,7.f);
}

void ATempleBotController::Reposition(ATempleFighter* Self,ATempleMatchMode* Mode,float Now)
{
    bFollowingPatrol=false;
    const FVector Here=Self->GetActorLocation();
    const FVector To=(LastSeen-Here).GetSafeNormal2D();
    const FVector Side=FVector(-To.Y,To.X,0);
    const float Distance=FVector::Dist2D(Here,LastSeen);
    FVector Separation=FVector::ZeroVector;
    for (TActorIterator<ATempleFighter> It(GetWorld());It;++It)
    {
        if (*It==Self || It->GetTeam()!=Self->GetTeam() || !It->IsAlive()) continue;
        const FVector Gap=Here-It->GetActorLocation();
        if (Gap.SizeSquared2D()<FMath::Square(360.f)) Separation+=Gap.GetSafeNormal2D()*(360.f-Gap.Size2D());
    }
    const float Advance=Distance>4000.f?FMath::FRandRange(1100.f,1550.f):
        Distance>2150.f?FMath::FRandRange(500.f,950.f):(Distance<620.f?-320.f:90.f);
    const float Lateral=FMath::FRandRange(250.f,510.f)*(FMath::RandBool()?1.f:-1.f);
    for (float Sign : {1.f,-1.f})
    {
        const FVector Goal=Here+To*Advance+Side*(Lateral*Sign)+Separation.GetClampedToMaxSize(290.f);
        if (!Mode->IsEnemySafeZone(Self->GetTeam(),Goal) && MoveToGround(Goal,46.f)) break;
    }
    NextReposition=Now+FMath::FRandRange(1.3f,2.7f);
}

void ATempleBotController::Think(ATempleFighter* Self,ATempleMatchMode* Mode,float Now)
{
    FVector Eye; FRotator View; Self->GetActorEyesViewPoint(Eye,View);
    const FVector Forward=View.Vector();
    ATempleFighter* Chosen=nullptr; FVector Seen=FVector::ZeroVector;
    float Best=MAX_FLT;
    for (TActorIterator<ATempleFighter> It(GetWorld());It;++It)
    {
        FVector Point;
        if (!VisibleTarget(Self,*It,Eye,Forward,Mode,Point)) continue;
        float Rank=FVector::DistSquared(Eye,Point);
        if (Target.Get()==*It) Rank*=.60f;
        if (Rank<Best) { Best=Rank; Chosen=*It; Seen=Point; }
    }
    if (!Chosen)
    {
        bTracking=false;
        if (Self->GetLastDamageTime()>LastDamageNotice)
            LastDamageNotice=Self->GetLastDamageTime();
        if (Now-LastDamageNotice<.65f && !Self->GetLastDamageDirection().IsNearlyZero())
        {
            bTracking=true;
            AimPoint=Eye+Self->GetLastDamageDirection()*1200;
        }
        if (bBurst) { Self->SetTriggerHeld(false); bBurst=false; }
        const bool bOnDistantFlank=bFollowingPatrol && PatrolLane>0 && FVector::DistSquared2D(Self->GetActorLocation(),LastSeen)>FMath::Square(3200.f);
        if (Target.IsValid() && Target->IsAlive() && !bLastSeenInEnemyBase && !bOnDistantFlank && Now-SeenTime<MemorySeconds)
        {
            if (!bSearching) { bSearching=true; MoveToGround(LastSeen,110.f); }
            return;
        }
        Target.Reset(); bSearching=false;
        Self->SetAiming(false);
        Patrol(Self,Mode,Now); return;
    }
    const bool New=Target.Get()!=Chosen || Now-SeenTime>.65f;
    if (New)
    {
        ReactAt=Now+FMath::FRandRange(ReactionRange.X,ReactionRange.Y);
        NextBurst=ReactAt; bBurst=false; Self->SetTriggerHeld(false);
        NextReposition=Now+FMath::FRandRange(.05f,.5f);
    }
    Target=Chosen; SeenTime=Now; LastSeen=Seen; bTracking=true; bSearching=false;
    bLastSeenInEnemyBase=Mode->IsEnemySafeZone(Self->GetTeam(),Chosen->GetActorLocation());
    const float Range=FVector::Distance(Seen,Eye);
    const float Error=(15.f+Range*.007f)*AimWobble;
    const FVector Side=FVector::CrossProduct((Seen-Eye).GetSafeNormal(),FVector::UpVector);
    AimPoint=Seen+Side*(FMath::Sin(Now*3.7f+Personality)*Error)+FVector(0,0,FMath::Cos(Now*2.8f+Personality)*Error*.55f);
    Self->SetAiming(Range>1150.f && !Self->IsReloading());
    if (bLastSeenInEnemyBase)
    {
        if (GetMoveStatus()!=EPathFollowingStatus::Idle) StopMovement();
        bHasMoveGoal=false;
        bFollowingPatrol=false;
    }
    else if (Now>=NextReposition)
    {
        if(PatrolLane>0 && Range>3200.f)
        {
            // Distant contact can be engaged while the flanker continues towards the next landmark.
            Patrol(Self,Mode,Now);
            NextReposition=Now+.6f;
        }
        else Reposition(Self,Mode,Now);
    }
    if (Self->GetMagazineAmmo()==0 || (Self->GetMagazineAmmo()<7 && New && Range>1800)) Self->StartReload();
    if (Self->IsReloading()) { Self->SetTriggerHeld(false); bBurst=false; NextBurst=Now+.15f; return; }
    if (bBurst && Now>=BurstUntil)
    {
        Self->SetTriggerHeld(false); bBurst=false;
        NextBurst=Now+(Range>4000.f?FMath::FRandRange(1.15f,1.9f):FMath::FRandRange(.24f,.74f));
    }
    const float Dot=FVector::DotProduct(Forward,(AimPoint-Eye).GetSafeNormal());
    if (!bBurst && Now>=ReactAt && Now>=NextBurst && Dot>.992f)
    {
        Self->SetTriggerHeld(true); bBurst=true;
        BurstUntil=Now+(Range>4000.f?FMath::FRandRange(.09f,.16f):FMath::FRandRange(.20f,.53f));
    }
}

void ATempleBotController::Tick(float Dt)
{
    Super::Tick(Dt);
    ATempleFighter* Self=Cast<ATempleFighter>(GetPawn());
    if (!HasAuthority() || !Self || !Self->IsAlive() || Self->GetTeam()>1) return;
    ATempleMatchMode* Mode=GetWorld()->GetAuthGameMode<ATempleMatchMode>();
    const float Now=GetWorld()->GetTimeSeconds();
    if(!Mode){CheckMovementProgress(Self,nullptr,Now);return;}
    if (!Mode->IsCombatActive())
    {
        if (bWasActive) { Self->SetTriggerHeld(false); StopMovement(); bTracking=false; bBurst=false; bHasMoveGoal=false; bWasActive=false; }
        return;
    }
    bWasActive=true;
    if (Now<NextSense) return;
    NextSense=Now+FMath::FRandRange(.13f,.20f);
    CheckMovementProgress(Self,Mode,Now);
    Think(Self,Mode,Now);
#if !UE_BUILD_SHIPPING
    static const bool bReview = FParse::Param(FCommandLine::Get(),TEXT("TempleSenseReview"));
    if (bReview && Self->ActorHasTag(TEXT("TempleSenseSubject")))
    {
        UE_LOG(LogTemp,Display,TEXT("TempleSense t=%.3f target=%s track=%d search=%d patrol=%d burst=%d seen=%.3f react=%.3f goal=(%.1f,%.1f) last=(%.1f,%.1f) ammo=%d reaction_range=(%.2f,%.2f) memory=%.2f"),
            Now,*GetNameSafe(Target.Get()),bTracking,bSearching,bFollowingPatrol,bBurst,SeenTime,ReactAt,
            MoveGoal.X,MoveGoal.Y,LastSeen.X,LastSeen.Y,Self->GetMagazineAmmo(),ReactionRange.X,ReactionRange.Y,MemorySeconds);
    }
#endif
}

void ATempleBotController::UpdateControlRotation(float Dt,bool bUpdatePawn)
{
    ATempleFighter* Self=Cast<ATempleFighter>(GetPawn());
    if (!bTracking || !Self) { Super::UpdateControlRotation(Dt,bUpdatePawn); return; }
    const FRotator Desired=(AimPoint-Self->GetPawnViewLocation()).Rotation();
    const FRotator New=FMath::RInterpConstantTo(GetControlRotation(),Desired,Dt,AimTurnDegreesPerSecond);
    SetControlRotation(New);
    if (bUpdatePawn) Self->FaceRotation(New,Dt);
}
