#include "TempleMuzzleLight.h"
#include "Camera/CameraComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/World.h"
#include "NiagaraComponent.h"

namespace
{
const FName MuzzleSocket(TEXT("Muzzle"));
}

UTempleMuzzleLight::UTempleMuzzleLight()
{
    PrimaryComponentTick.bCanEverTick = true;
    PrimaryComponentTick.bStartWithTickEnabled = false;
    PrimaryComponentTick.TickGroup = TG_PostUpdateWork;
}

void UTempleMuzzleLight::StartFlash(USkeletalMeshComponent* Gun, UCameraComponent* OwnerCamera, UNiagaraComponent* Burst, const FRotator& Aim)
{
    Weapon = Gun;
    Camera = OwnerCamera;
    Particles = Burst;
    StartedAt = GetWorld()->GetTimeSeconds();
    if (Camera)
    {
        AttachToComponent(Camera, FAttachmentTransformRules::KeepRelativeTransform);
        FollowViewSocket();
    }
    else
    {
        AttachToComponent(Weapon, FAttachmentTransformRules::SnapToTargetNotIncludingScale, MuzzleSocket);
        SetRelativeLocation(FVector::ZeroVector);
        SetWorldRotation(Aim);
        SetWorldScale3D(FVector::OneVector);
    }
    SetVisibility(true);
    SetComponentTickEnabled(true);
    if (Particles->GetAsset()) Particles->Activate(true);
}

void UTempleMuzzleLight::FollowViewSocket()
{
    // Finish after the arms and camera so recoil, weapon FOV and strafing share the rendered barrel transform.
    FMinimalViewInfo View;
    Camera->GetCameraView(0.f, View);
    const FVector Socket = Weapon->GetSocketLocation(MuzzleSocket);
    const FVector Origin = View.TransformWorldToFirstPerson(Socket, false);
    const FVector Bore = Weapon->GetComponentTransform().GetUnitAxis(EAxis::Y);
    const FVector End = View.TransformWorldToFirstPerson(Socket + 20.f * Bore, false);
    SetWorldLocationAndRotation(Origin, (End - Origin).Rotation());
    SetWorldScale3D(FVector(View.FirstPersonScale));
}

void UTempleMuzzleLight::TickComponent(float Delta, ELevelTick TickType, FActorComponentTickFunction* ThisTick)
{
    Super::TickComponent(Delta, TickType, ThisTick);
    if (Camera) FollowViewSocket();
    const double Age = GetWorld()->GetTimeSeconds() - StartedAt;
    if (Age >= .045 && IsVisible()) SetVisibility(false);
    // The last sprite in NS_CarbineMuzzle expires at 61 ms. Its emitter runs out its own loop.
    if (Age >= .080) SetComponentTickEnabled(false);
}

void UTempleMuzzleLight::StopFlash()
{
    SetVisibility(false);
    SetComponentTickEnabled(false);
    if (Particles) Particles->DeactivateImmediate();
}
