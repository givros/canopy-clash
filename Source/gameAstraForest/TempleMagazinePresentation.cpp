#include "TempleMagazinePresentation.h"
#include "TempleFighter.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "UObject/ConstructorHelpers.h"

UTempleMagazinePresentation::UTempleMagazinePresentation()
{
    const ConstructorHelpers::FObjectFinder<UStaticMesh> Mesh(TEXT("/Game/TempleTDM/Presentation/SM_CanopyMagazine.SM_CanopyMagazine"));
    SetStaticMesh(Mesh.Object);
    SetCollisionProfileName(TEXT("NoCollision"));
    SetCanEverAffectNavigation(false);
    SetGenerateOverlapEvents(false);
    PrimaryComponentTick.bCanEverTick=true;
    PrimaryComponentTick.bStartWithTickEnabled=false;
    PrimaryComponentTick.bAllowTickOnDedicatedServer=false;
    PrimaryComponentTick.TickGroup=TG_PostUpdateWork;
}

void UTempleMagazinePresentation::BeginPlay()
{
    Super::BeginPlay();
    Fighter=Cast<ATempleFighter>(GetOwner());
    Weapon=Cast<USkeletalMeshComponent>(GetAttachParent());
    if (!HandRig) SetHandRig(Weapon?Cast<USkeletalMeshComponent>(Weapon->GetAttachParent()):nullptr);
    if(Weapon) AddTickPrerequisiteComponent(Weapon);
    if(GetStaticMesh()) Center=GetStaticMesh()->GetBoundingBox().GetCenter();
}

void UTempleMagazinePresentation::SetHandRig(USkeletalMeshComponent* NewRig, const FQuat& SourceHandInRig)
{
    if (HandRig) RemoveTickPrerequisiteComponent(HandRig);
    HandRig = NewRig;
    SourceHandBasis = SourceHandInRig;
    if (HandRig) AddTickPrerequisiteComponent(HandRig);
}

void UTempleMagazinePresentation::PlayReload(float Duration)
{
    if(!HandRig || !Weapon || !Fighter || !GetStaticMesh() || Duration<=0.f) return;
    StartTime=GetWorld()->GetTimeSeconds();
    ClipDuration=Duration;
    SetComponentTickEnabled(true);
}

void UTempleMagazinePresentation::TickComponent(float Delta,ELevelTick TickType,FActorComponentTickFunction* ThisTick)
{
    Super::TickComponent(Delta,TickType,ThisTick);
    const float Phase=(GetWorld()->GetTimeSeconds()-StartTime)/ClipDuration;
    // At seating, returning to the model's exact source transform also avoids idle animation cost.
    if(Phase>=.675f || !Fighter->IsAlive() || !Fighter->CombatActive())
    {
        SetRelativeTransform(FTransform::Identity);
        SetComponentTickEnabled(false);
        return;
    }
    const float Weight=FMath::SmoothStep(.095f,.152f,Phase)*(1.f-FMath::SmoothStep(.615f,.675f,Phase));
    if(Weight<=0.f) return;
    const FTransform& Gun=Weapon->GetComponentTransform();
    const FTransform Hand=HandRig->GetSocketTransform(TEXT("hand_l"));
    const FVector Fingers=HandRig->GetSocketLocation(TEXT("middle_02_l"));
    const FVector Thumb=HandRig->GetSocketLocation(TEXT("thumb_03_l"));
    const FVector LocalGripPosition=Gun.InverseTransformPosition(FMath::Lerp(Fingers,Thumb,.48f));
    // Relative grip orientations sampled from MM_Rifle_Reload at its two contact poses.
    const FQuat Pickup(.595325,.722647,.345014,-.065837);
    const FQuat Return(.686643,.565990,-.261132,.374149);
    const FQuat InHand=FQuat::Slerp(Pickup,Return,FMath::SmoothStep(.255f,.415f,Phase)).GetNormalized();
    const FQuat Held=(Gun.GetRotation().Inverse()*Hand.GetRotation()*SourceHandBasis*InHand).GetNormalized();
    const FQuat Rotation=FQuat::Slerp(FQuat::Identity,Held,Weight);
    const FVector Location=FMath::Lerp(Center,LocalGripPosition,Weight)-Rotation.RotateVector(Center);
    SetRelativeLocationAndRotation(Location,Rotation);
}
