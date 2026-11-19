#include "TempleDeploymentNavigation.h"
#include "TempleFighter.h"
#include "AI/Navigation/NavQueryFilter.h"
#include "AI/NavigationModifier.h"
#include "Components/CapsuleComponent.h"
#include "NavAreas/NavArea_Default.h"
#include "NavigationOctree.h"

UTempleRedDeploymentArea::UTempleRedDeploymentArea(const FObjectInitializer& Initializer) : Super(Initializer)
{
    DrawColor = FColor(190, 49, 46);
}

UTempleBlueDeploymentArea::UTempleBlueDeploymentArea(const FObjectInitializer& Initializer) : Super(Initializer)
{
    DrawColor = FColor(49, 116, 201);
}

void UTempleDeploymentRouteFilter::InitializeFilter(const ANavigationData& NavData, const UObject* Querier, FNavigationQueryFilter& Filter) const
{
    Super::InitializeFilter(NavData, Querier, Filter);
    // Opposing deployment can require an entire circuit through the west cloister.
    Filter.SetMaxSearchNodes(FMath::Max(Filter.GetMaxSearchNodes(), 8192u));
}

UTempleRedRouteFilter::UTempleRedRouteFilter(const FObjectInitializer& Initializer) : Super(Initializer)
{
    AddExcludedArea(UTempleBlueDeploymentArea::StaticClass());
}

UTempleBlueRouteFilter::UTempleBlueRouteFilter(const FObjectInitializer& Initializer) : Super(Initializer)
{
    AddExcludedArea(UTempleRedDeploymentArea::StaticClass());
}

ATempleDeploymentNavigation::ATempleDeploymentNavigation(const FObjectInitializer& Initializer) : Super(Initializer)
{
    AreaClass = UTempleRedDeploymentArea::StaticClass();
    AreaClassToReplace = UNavArea_Default::StaticClass();
    SetActorEnableCollision(false);
}

FBox ATempleDeploymentNavigation::GetNavigationBounds() const
{
    // Navigation tests the feet, while the gameplay boundary tests the capsule center.
    const float FeetOffset = GetDefault<ATempleFighter>()->GetCapsuleComponent()->GetUnscaledCapsuleHalfHeight();
    const FVector Center = GetActorLocation();
    const FVector RadialExtent(TempleNavigation::SpawnRadius, TempleNavigation::SpawnRadius, 0);
    return FBox(Center - RadialExtent - FVector(0, 0, TempleNavigation::SpawnHalfHeight + FeetOffset),
                Center + RadialExtent + FVector(0, 0, TempleNavigation::SpawnHalfHeight));
}

void ATempleDeploymentNavigation::GetNavigationData(FNavigationRelevantData& Data) const
{
    if (!AreaClass) return;
    const FBox Bounds = GetNavigationBounds();
    const FVector Center = GetActorLocation();
    const FVector Bottom(Center.X, Center.Y, Bounds.Min.Z);
    FAreaNavModifier Footprint(TempleNavigation::SpawnRadius, float(Bounds.Max.Z - Bounds.Min.Z), FTransform(Bottom), AreaClass);
    Footprint.SetAreaClassToReplace(UNavArea_Default::StaticClass());
    Data.Modifiers.Add(Footprint);
}
