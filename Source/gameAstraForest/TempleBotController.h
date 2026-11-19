#pragma once

#include "CoreMinimal.h"
#include "AIController.h"
#include "TempleBotController.generated.h"

class ATempleFighter;
class ATempleMatchMode;

UCLASS()
class GAMEASTRAFOREST_API ATempleBotController : public AAIController
{
    GENERATED_BODY()
public:
    static constexpr int32 FirstRosterPlayerId = 10001;
    static constexpr uint8 AppearanceCount = 5;
    uint8 GetAppearanceSlot() const { return AppearanceSlot; }
    void SetAppearanceSlot(uint8 Slot) { check(Slot < AppearanceCount); AppearanceSlot = Slot; }
    ATempleBotController(const FObjectInitializer& ObjectInitializer);
    virtual void Tick(float DeltaSeconds) override;
    virtual void UpdateControlRotation(float DeltaSeconds,bool bUpdatePawn=true) override;
protected:
    virtual void OnPossess(APawn* Pawn) override;
    virtual void OnUnPossess() override;
    UPROPERTY(EditDefaultsOnly,Category="Awareness") float SightDistance=7400.f;
    UPROPERTY(EditDefaultsOnly,Category="Awareness") float MemorySeconds=3.3f;
    UPROPERTY(EditDefaultsOnly,Category="Awareness") float PeripheralHalfAngle=76.f;
    UPROPERTY(EditDefaultsOnly,Category="Combat") float AimTurnDegreesPerSecond=170.f;
    UPROPERTY(EditDefaultsOnly,Category="Combat") FVector2D ReactionRange=FVector2D(.30f,.70f);
private:
    uint8 AppearanceSlot = 0;
    int32 PatrolLane=INDEX_NONE,PatrolStation=INDEX_NONE,PatrolDirection=1;
    bool bFollowingPatrol=false;
    TWeakObjectPtr<ATempleFighter> Target;
    FVector LastSeen=FVector::ZeroVector;
    FVector AimPoint=FVector::ZeroVector;
    FVector MoveGoal=FVector::ZeroVector;
    FVector LastProgressLocation=FVector::ZeroVector;
    float SeenTime=-1000.f;
    float NextSense=0.f;
    float NextReposition=0.f;
    float NextProgressCheck=0.f;
    float YieldUntil=0.f;
    float ResumeAcceptance=0.f;
    bool bResumeStopOnOverlap=false;
    float ContinuousMoveSince=-1.f;
    FVector ResumeDestination=FVector::ZeroVector;
    float ReactAt=0.f;
    float BurstUntil=0.f;
    float NextBurst=0.f;
    float Personality=0.f;
    float AimWobble=0.f;
    float LastDamageNotice=-1000.f;
    bool bTracking=false;
    bool bSearching=false;
    bool bLastSeenInEnemyBase=false;
    bool bBurst=false;
    bool bHasMoveGoal=false;
    bool bWasActive=false;
    bool VisibleTarget(ATempleFighter* Self,ATempleFighter* Other,const FVector& Eye,const FVector& Forward,const ATempleMatchMode* Mode,FVector& OutSeen) const;
    bool MoveToGround(const FVector& Destination,float Acceptance);
    void CheckMovementProgress(ATempleFighter* Self,ATempleMatchMode* Mode,float Now);
    bool TryYieldToTeammate(ATempleFighter* Self,ATempleMatchMode* Mode,float Now);
    void Think(ATempleFighter* Self,ATempleMatchMode* Mode,float Now);
    void Patrol(ATempleFighter* Self,ATempleMatchMode* Mode,float Now);
    void Reposition(ATempleFighter* Self,ATempleMatchMode* Mode,float Now);
};
