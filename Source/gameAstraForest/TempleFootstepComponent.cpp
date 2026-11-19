#include "TempleFootstepComponent.h"
#include "TempleFighter.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "Kismet/GameplayStatics.h"
#include "LandscapeHeightfieldCollisionComponent.h"
#include "Sound/SoundAttenuation.h"
#include "Sound/SoundWave.h"
#include "UObject/ConstructorHelpers.h"

UTempleFootstepComponent::UTempleFootstepComponent()
{
    PrimaryComponentTick.bCanEverTick = true;
    PrimaryComponentTick.TickGroup = TG_PostPhysics;
    PrimaryComponentTick.TickInterval = .033f;
    PrimaryComponentTick.bAllowTickOnDedicatedServer = false;
    for (int32 Index = 1; Index <= 3; ++Index)
    {
        auto FindWave = [Index](const TCHAR* Surface)
        {
            const FString Name = FString::Printf(TEXT("S_Step%s%02d"), Surface, Index);
            const FString Path = TEXT("/Game/TempleTDM/Feedback/Footsteps/") + Name + TEXT(".") + Name;
            return ConstructorHelpers::FObjectFinder<USoundWave>(*Path).Object;
        };
        ForestSounds.Add(FindWave(TEXT("Forest")));
        StoneSounds.Add(FindWave(TEXT("Stone")));
    }
    Attenuation = CreateDefaultSubobject<USoundAttenuation>(TEXT("FootfallAttenuation"));
    FSoundAttenuationSettings& Settings = Attenuation->Attenuation;
    Settings.bAttenuate = true;
    Settings.bSpatialize = true;
    Settings.AttenuationShapeExtents.X = 165.f;
    Settings.FalloffDistance = 1500.f;
    Settings.DistanceAlgorithm = EAttenuationDistanceModel::NaturalSound;
    Settings.dBAttenuationAtMax = -44.f;
}

void UTempleFootstepComponent::BeginPlay()
{
    Super::BeginPlay();
    Fighter = Cast<ATempleFighter>(GetOwner());
    if (!Fighter || GetNetMode() == NM_DedicatedServer)
    {
        SetComponentTickEnabled(false);
        return;
    }
    AddTickPrerequisiteComponent(Fighter->GetCharacterMovement());
    PreviousLocation = Fighter->GetActorLocation();
}

void UTempleFootstepComponent::TickComponent(float Delta, ELevelTick TickType, FActorComponentTickFunction* ThisTick)
{
    Super::TickComponent(Delta, TickType, ThisTick);
    const FVector Location = Fighter->GetActorLocation();
    const float Distance = FVector::Dist2D(Location, PreviousLocation);
    PreviousLocation = Location;
    const float Speed = Fighter->GetVelocity().Size2D();
    if (!Fighter->IsAlive() || !Fighter->GetCharacterMovement()->IsMovingOnGround() ||
        Distance > FMath::Max(100.f, Speed * Delta * 2.5f))
    {
        Phase = .45f;
        StationaryTime = 0.f;
        return;
    }
    if (Speed < 25.f || Distance < .3f)
    {
        StationaryTime += Delta;
        if (StationaryTime > .13f) Phase = .45f;
        return;
    }
    StationaryTime = 0.f;
    const float Interval = Fighter->bIsCrouched ? .50f :
        FMath::GetMappedRangeValueClamped(FVector2D(180.f, 690.f), FVector2D(.49f, .315f), Speed);
    Phase += Distance / FMath::Max(55.f, Speed * Interval);
    if (Phase >= 1.f)
    {
        Phase = FMath::Fmod(Phase, 1.f);
        PlayStep(Speed);
    }
}

void UTempleFootstepComponent::PlayStep(float Speed)
{
    const FVector Feet = Fighter->GetCharacterMovement()->GetActorFeetLocation();
    bLeft = !bLeft;
    if (!UGameplayStatics::AreAnyListenersWithinRange(this, Feet, 1670.f)) return;
    const UPrimitiveComponent* Surface = Cast<UPrimitiveComponent>(Fighter->GetMovementBaseObject());
    if (!Surface)
    {
        FHitResult Hit;
        const FCollisionQueryParams Query(SCENE_QUERY_STAT(TempleFootSupport), false, Fighter);
        GetWorld()->LineTraceSingleByChannel(Hit, Feet + FVector(0,0,20), Feet - FVector(0,0,65), ECC_Visibility, Query);
        Surface = Hit.GetComponent();
    }
    if (!Surface) return;
    const bool bForest = Surface->IsA<ULandscapeHeightfieldCollisionComponent>() || Surface->ComponentHasTag(TEXT("FootstepForest"));
    int32& Last = bForest ? LastForest : LastStone;
    const auto& Sounds = bForest ? ForestSounds : StoneSounds;
    Last = Last == INDEX_NONE ? FMath::RandRange(0, Sounds.Num()-1) : (Last + FMath::RandRange(1,Sounds.Num()-1)) % Sounds.Num();
    if (!Sounds[Last]) return;
    const float Gain = Fighter->bIsCrouched ? .082f :
        FMath::GetMappedRangeValueClamped(FVector2D(150.f,690.f), FVector2D(.135f,.26f), Speed);
    const FVector At = Feet + Fighter->GetActorRightVector() * (bLeft ? -8.f : 8.f) + FVector(0,0,4);
    UGameplayStatics::PlaySoundAtLocation(this, Sounds[Last], At, Gain, FMath::FRandRange(.945f,1.065f), 0.f, Attenuation);
#if !UE_BUILD_SHIPPING
    static const bool bReview = FParse::Param(FCommandLine::Get(),TEXT("TempleAudioReview"));
    if (bReview)
    {
        UE_LOG(LogTemp,Display,TEXT("TempleStep time=%.3f subject=%s controlled=%d sample=%s gain=%.3f speed=%.1f surface=%s"),
            GetWorld()->GetTimeSeconds(), *Fighter->GetName(), Fighter->IsPlayerControlled(), *Sounds[Last]->GetName(),
            Gain, Speed, *Surface->GetClass()->GetName());
    }
#endif
}
