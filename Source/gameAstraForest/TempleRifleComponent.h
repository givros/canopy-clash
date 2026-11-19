#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "TempleRifleComponent.generated.h"

class ATempleFighter;

UCLASS(ClassGroup=(Combat),meta=(BlueprintSpawnableComponent))
class GAMEASTRAFOREST_API UTempleRifleComponent : public UActorComponent
{
    GENERATED_BODY()
public:
    UTempleRifleComponent();
    virtual void GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const override;
    virtual void EndPlay(const EEndPlayReason::Type Reason) override;
    void SetHeld(bool Held, int32 PullId=0);
    int32 SetLocalHeld(bool Held);
    bool IsLocalTriggerHeld() const { return bLocalHeld; }
    bool NeedsOwnerPresentation(int32 PullId,int32 ShotIndex);
    void CloseLocalPull(int32 PullId,int32 AuthoritativeAmmo);
    bool RequestLocalReload();
    void RejectLocalReload() { bAwaitingReload=false; }
    void BeginReload();
    void Cancel();
    int32 GetAmmo() const { return Ammo; }
    int32 GetReserve() const { return Reserve; }
    int32 GetCapacity() const { return Capacity; }
    bool IsReloading() const { return ReloadEnd>0.f; }
    float ReloadAlpha() const;
    float GetReloadDuration() const { return ReloadSeconds; }
protected:
    virtual void BeginPlay() override;
    UPROPERTY(EditDefaultsOnly,Category="Carbine",meta=(ClampMin="1")) int32 Capacity=30;
    UPROPERTY(EditDefaultsOnly,Category="Carbine",meta=(ClampMin="0")) int32 StartingReserve=120;
    UPROPERTY(EditDefaultsOnly,Category="Carbine",meta=(ClampMin="0.06")) float FireInterval=.14f;
    UPROPERTY(EditDefaultsOnly,Category="Carbine",meta=(ClampMin="0.2")) float ReloadSeconds=1.95f;
    UPROPERTY(EditDefaultsOnly,Category="Carbine") float BodyDamage=24.f;
    UPROPERTY(EditDefaultsOnly,Category="Carbine") float HeadDamage=48.f;
    UPROPERTY(EditDefaultsOnly,Category="Carbine") float TraceDistance=14500.f;
private:
    UPROPERTY(ReplicatedUsing=OnRep_Ammo) int32 Ammo=30;
    UPROPERTY(Replicated) int32 Reserve=120;
    UPROPERTY(ReplicatedUsing=OnRep_ReloadEnd) float ReloadEnd=0.f;
    UPROPERTY() TObjectPtr<ATempleFighter> Fighter;
    FTimerHandle FireTimer;
    FTimerHandle ReloadTimer;
    float LastShot=-1000.f;
    bool bHeld=false;
    int32 ServerPullId=0,ServerShotIndex=0;
    struct FOwnerPull
    {
        int32 Id=0,Presented=0,Confirmed=0;
        bool bClosed=false;
    };
    TArray<FOwnerPull> OwnerPulls;
    int32 LocalPullId=0,LocalBudget=INDEX_NONE;
    bool bLocalHeld=false,bAwaitingReload=false;
    float LastOwnerPresentation=-1000.f;
    FTimerHandle PresentationTimer;
    void TryOwnerPresentation();
    void ScheduleOwnerPresentation();
    UFUNCTION() void OnRep_Ammo(int32 Previous);
    UFUNCTION() void OnRep_ReloadEnd(float Previous);
    void Shoot();
    void FinishReload();
};
