#include "TempleRifleComponent.h"
#include "TempleFighter.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "Kismet/GameplayStatics.h"
#include "Net/UnrealNetwork.h"
#include "TimerManager.h"

UTempleRifleComponent::UTempleRifleComponent()
{
    SetIsReplicatedByDefault(true);
    PrimaryComponentTick.bCanEverTick=false;
}

void UTempleRifleComponent::BeginPlay()
{
    Super::BeginPlay();
    Fighter=CastChecked<ATempleFighter>(GetOwner());
    if (GetOwner()->HasAuthority()) { Ammo=Capacity; Reserve=StartingReserve; }
}

void UTempleRifleComponent::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const
{
    Super::GetLifetimeReplicatedProps(OutLifetimeProps);
    DOREPLIFETIME_CONDITION(UTempleRifleComponent,Ammo,COND_OwnerOnly);
    DOREPLIFETIME_CONDITION(UTempleRifleComponent,Reserve,COND_OwnerOnly);
    DOREPLIFETIME(UTempleRifleComponent,ReloadEnd);
}

void UTempleRifleComponent::EndPlay(const EEndPlayReason::Type Reason)
{
    Cancel();
    Super::EndPlay(Reason);
}

void UTempleRifleComponent::Cancel()
{
    bHeld=false;
    bLocalHeld=false; bAwaitingReload=false;
    if (UWorld* World=GetWorld())
    {
        World->GetTimerManager().ClearTimer(FireTimer);
        World->GetTimerManager().ClearTimer(ReloadTimer);
        World->GetTimerManager().ClearTimer(PresentationTimer);
    }
    if (GetOwner() && GetOwner()->HasAuthority()) ReloadEnd=0.f;
}

void UTempleRifleComponent::SetHeld(bool Held,int32 PullId)
{
    if (!Fighter || !Fighter->HasAuthority() || bHeld==Held) return;
    bHeld=Held;
    if (!Held) { GetWorld()->GetTimerManager().ClearTimer(FireTimer); return; }
    ServerPullId=PullId; ServerShotIndex=0;
    Shoot();
}

int32 UTempleRifleComponent::SetLocalHeld(bool Held)
{
    if (bLocalHeld==Held) return LocalPullId;
    bLocalHeld=Held;
    if (Held)
    {
        LocalPullId=LocalPullId==MAX_int32?1:LocalPullId+1;
        // Retain recently closed pulls so delayed multicast packets cannot replay their effects.
        if (OwnerPulls.Num()>=64) OwnerPulls.RemoveAt(0);
        OwnerPulls.Add({LocalPullId});
        if (LocalBudget==INDEX_NONE) LocalBudget=Ammo;
        TryOwnerPresentation();
    }
    else GetWorld()->GetTimerManager().ClearTimer(PresentationTimer);
    return LocalPullId;
}

void UTempleRifleComponent::ScheduleOwnerPresentation()
{
    if (!bLocalHeld || GetWorld()->GetTimerManager().IsTimerActive(PresentationTimer)) return;
    const float Wait=FMath::Max(.001f,LastOwnerPresentation+FireInterval-GetWorld()->GetTimeSeconds());
    GetWorld()->GetTimerManager().SetTimer(PresentationTimer,this,&UTempleRifleComponent::TryOwnerPresentation,Wait);
}

void UTempleRifleComponent::TryOwnerPresentation()
{
    GetWorld()->GetTimerManager().ClearTimer(PresentationTimer);
    if (!bLocalHeld || !Fighter || !Fighter->IsAlive() || !Fighter->CombatActive() || bAwaitingReload ||
        IsReloading() || Ammo<=0 || LocalBudget<=0 || OwnerPulls.IsEmpty()) return;
    FOwnerPull& Pull=OwnerPulls.Last();
    // A lost packet may delay the next presentation. The server still drives every actual round.
    if (Pull.Presented>Pull.Confirmed) return;
    const float Now=GetWorld()->GetTimeSeconds();
    if (Now+KINDA_SMALL_NUMBER<LastOwnerPresentation+FireInterval) { ScheduleOwnerPresentation();return; }
    ++Pull.Presented; --LocalBudget;
    LastOwnerPresentation=Now;
    Fighter->PlayShotPresentation(Fighter->GetBaseAimRotation());
    ScheduleOwnerPresentation();
}

bool UTempleRifleComponent::NeedsOwnerPresentation(int32 PullId,int32 ShotIndex)
{
    auto* Pull=OwnerPulls.FindByPredicate([PullId](const FOwnerPull& Item){return Item.Id==PullId;});
    if (!Pull) return PullId==0;
    Pull->Confirmed=FMath::Max(Pull->Confirmed,ShotIndex);
    const bool bNew=ShotIndex>Pull->Presented;
    if (bNew)
    {
        if (!Pull->bClosed) LocalBudget=FMath::Max(0,LocalBudget-(ShotIndex-Pull->Presented));
        Pull->Presented=ShotIndex;
        LastOwnerPresentation=GetWorld()->GetTimeSeconds();
    }
    if (bLocalHeld && PullId==LocalPullId) ScheduleOwnerPresentation();
    return bNew;
}

void UTempleRifleComponent::CloseLocalPull(int32 PullId,int32 AuthoritativeAmmo)
{
    const int32 Index=OwnerPulls.IndexOfByPredicate([PullId](const FOwnerPull& Item){return Item.Id==PullId;});
    if (Index==INDEX_NONE) return;
    OwnerPulls[Index].bClosed=true;
    int32 LaterShots=0;
    for (int32 I=Index+1;I<OwnerPulls.Num();++I) LaterShots+=OwnerPulls[I].Presented;
    LocalBudget=FMath::Max(0,AuthoritativeAmmo-LaterShots);
}

bool UTempleRifleComponent::RequestLocalReload()
{
    if (bAwaitingReload || IsReloading() || Reserve<=0 ||
        (Ammo>=Capacity && (LocalBudget==INDEX_NONE || LocalBudget>=Capacity))) return false;
    bAwaitingReload=true;
    return true;
}

void UTempleRifleComponent::OnRep_Ammo(int32 Previous)
{
    LocalBudget=Ammo>Previous || LocalBudget==INDEX_NONE ? Ammo : FMath::Min(Ammo,LocalBudget);
    if (Ammo>Previous) bAwaitingReload=false;
}

void UTempleRifleComponent::OnRep_ReloadEnd(float Previous)
{
    if (Previous>0.f && !IsReloading()) { bAwaitingReload=false; LocalBudget=Ammo; }
}

void UTempleRifleComponent::Shoot()
{
    if (!bHeld || !Fighter || !Fighter->IsAlive() || !Fighter->CombatActive()) { bHeld=false; return; }
    if (IsReloading()) return;
    if (!Ammo) { BeginReload(); return; }
    const float Now=GetWorld()->GetTimeSeconds();
    const float Remaining=LastShot+FireInterval-Now;
    if (Remaining>KINDA_SMALL_NUMBER)
    {
        GetWorld()->GetTimerManager().SetTimer(FireTimer,this,&UTempleRifleComponent::Shoot,Remaining,false);
        return;
    }
    LastShot=Now;
    --Ammo;
    Fighter->FiredOnServer();
    FVector Eye; FRotator Rotation;
    Fighter->GetActorEyesViewPoint(Eye,Rotation);
    const float MoveFraction=FMath::Clamp(Fighter->GetVelocity().Size2D()/520.f,0.f,1.f);
    const float ConeDegrees=(Fighter->IsAiming() ? .22f : .72f)+MoveFraction*.50f+(Fighter->GetCharacterMovement()->IsFalling()?1.45f:0.f);
    const FVector Direction=FMath::VRandCone(Rotation.Vector(),FMath::DegreesToRadians(ConeDegrees));
    FCollisionQueryParams Query(SCENE_QUERY_STAT(TempleCarbine),true,Fighter);
    FHitResult Hit;
    const FVector TraceEnd=Eye+Direction*TraceDistance;
    bool bHit=GetWorld()->LineTraceSingleByChannel(Hit,Eye,TraceEnd,ECC_Visibility,Query);
    FVector Destination=bHit?Hit.ImpactPoint:TraceEnd;
    const FVector WorldMuzzlePosition=Fighter->WorldMuzzle();
    // The view picks the sight point. The muzzle sweep catches objects immediately in front of the held weapon.
    FHitResult Obstruction;
    if (GetWorld()->LineTraceSingleByChannel(Obstruction,WorldMuzzlePosition,Destination,ECC_Visibility,Query))
    {
        Hit=Obstruction;
        Destination=Hit.ImpactPoint;
        bHit=true;
    }
    ATempleFighter* Victim=bHit?Cast<ATempleFighter>(Hit.GetActor()):nullptr;
    if (Victim && Victim->IsAlive())
    {
        const float Eyes=Victim->GetPawnViewLocation().Z;
        const bool bHead=(Hit.BoneName=="head" || (Hit.BoneName.IsNone() && Hit.ImpactPoint.Z>Eyes-9.f));
        const float Applied=UGameplayStatics::ApplyPointDamage(Victim,bHead?HeadDamage:BodyDamage,
            Direction,Hit,Fighter->GetController(),Fighter,UDamageType::StaticClass());
        if (Applied>0) Fighter->ClientConfirmHit(!IsValid(Victim) || !Victim->IsAlive());
    }
    Fighter->MulticastShot(Destination,bHit?Hit.ImpactNormal:-Direction,bHit,Victim!=nullptr,ServerPullId,++ServerShotIndex);
    Fighter->ForceNetUpdate();
    GetWorld()->GetTimerManager().SetTimer(FireTimer,this,&UTempleRifleComponent::Shoot,FireInterval,false);
}

void UTempleRifleComponent::BeginReload()
{
    if (!Fighter || !Fighter->HasAuthority() || !Fighter->IsAlive() || !Fighter->CombatActive() ||
        IsReloading() || Ammo>=Capacity || Reserve<=0) return;
    GetWorld()->GetTimerManager().ClearTimer(FireTimer);
    ReloadEnd=Fighter->ServerClock()+ReloadSeconds;
    Fighter->MulticastReload();
    Fighter->ForceNetUpdate();
    GetWorld()->GetTimerManager().SetTimer(ReloadTimer,this,&UTempleRifleComponent::FinishReload,ReloadSeconds,false);
}

void UTempleRifleComponent::FinishReload()
{
    ReloadEnd=0.f;
    if (!Fighter || !Fighter->IsAlive() || !Fighter->CombatActive()) { bHeld=false; return; }
    const int32 Transfer=FMath::Min(Capacity-Ammo,Reserve);
    Reserve-=Transfer; Ammo+=Transfer;
    Fighter->ForceNetUpdate();
    if (bHeld) Shoot();
}

float UTempleRifleComponent::ReloadAlpha() const
{
    return Fighter && IsReloading()?FMath::Clamp(1.f-(ReloadEnd-Fighter->ServerClock())/ReloadSeconds,0.f,1.f):0.f;
}
