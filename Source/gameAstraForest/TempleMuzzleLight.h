#pragma once

#include "Components/PointLightComponent.h"
#include "TempleMuzzleLight.generated.h"

class UCameraComponent;
class UNiagaraComponent;
class USkeletalMeshComponent;

UCLASS()
class GAMEASTRAFOREST_API UTempleMuzzleLight : public UPointLightComponent
{
    GENERATED_BODY()
public:
    UTempleMuzzleLight();
    void StartFlash(USkeletalMeshComponent* Gun, UCameraComponent* OwnerCamera, UNiagaraComponent* Burst, const FRotator& Aim);
    void StopFlash();
    virtual void TickComponent(float Delta, ELevelTick TickType, FActorComponentTickFunction* ThisTick) override;

private:
    void FollowViewSocket();
    UPROPERTY(Transient) TObjectPtr<UCameraComponent> Camera;
    UPROPERTY(Transient) TObjectPtr<USkeletalMeshComponent> Weapon;
    UPROPERTY(Transient) TObjectPtr<UNiagaraComponent> Particles;
    double StartedAt = 0.;
};
