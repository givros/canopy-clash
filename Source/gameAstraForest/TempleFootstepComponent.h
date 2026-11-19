#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "TempleFootstepComponent.generated.h"

class ATempleFighter;
class USoundAttenuation;
class USoundWave;

UCLASS()
class GAMEASTRAFOREST_API UTempleFootstepComponent : public UActorComponent
{
    GENERATED_BODY()
public:
    UTempleFootstepComponent();
    virtual void BeginPlay() override;
    virtual void TickComponent(float Delta, ELevelTick TickType, FActorComponentTickFunction* ThisTick) override;
private:
    UPROPERTY() TObjectPtr<ATempleFighter> Fighter;
    UPROPERTY() TObjectPtr<USoundAttenuation> Attenuation;
    UPROPERTY() TArray<TObjectPtr<USoundWave>> ForestSounds;
    UPROPERTY() TArray<TObjectPtr<USoundWave>> StoneSounds;
    FVector PreviousLocation = FVector::ZeroVector;
    float Phase = .45f;
    float StationaryTime = 0.f;
    int32 LastForest = INDEX_NONE;
    int32 LastStone = INDEX_NONE;
    bool bLeft = false;
    void PlayStep(float Speed);
};
