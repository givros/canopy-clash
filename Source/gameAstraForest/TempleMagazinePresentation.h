#pragma once

#include "CoreMinimal.h"
#include "Components/StaticMeshComponent.h"
#include "TempleMagazinePresentation.generated.h"

class ATempleFighter;
class USkeletalMeshComponent;

/** One rigid piece of the original model. Its transform follows the character's authored reload clip. */
UCLASS()
class GAMEASTRAFOREST_API UTempleMagazinePresentation : public UStaticMeshComponent
{
    GENERATED_BODY()
public:
    UTempleMagazinePresentation();
    void PlayReload(float Duration);
    void SetHandRig(USkeletalMeshComponent* NewRig, const FQuat& SourceHandInRig = FQuat::Identity);
    virtual void BeginPlay() override;
    virtual void TickComponent(float Delta,ELevelTick TickType,FActorComponentTickFunction* ThisTick) override;
private:
    UPROPERTY() TObjectPtr<ATempleFighter> Fighter;
    UPROPERTY() TObjectPtr<USkeletalMeshComponent> Weapon;
    UPROPERTY() TObjectPtr<USkeletalMeshComponent> HandRig;
    FQuat SourceHandBasis = FQuat::Identity;
    FVector Center=FVector::ZeroVector;
    float StartTime=0.f,ClipDuration=0.f;
};
