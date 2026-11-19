#pragma once

#include "NavAreas/NavArea.h"
#include "NavFilters/NavigationQueryFilter.h"
#include "NavModifierVolume.h"
#include "TempleDeploymentNavigation.generated.h"

namespace TempleNavigation
{
inline constexpr float SpawnRadius = 650.f;
inline constexpr float SpawnHalfHeight = 430.f;
}

UCLASS()
class GAMEASTRAFOREST_API UTempleRedDeploymentArea : public UNavArea
{
    GENERATED_BODY()
public:
    explicit UTempleRedDeploymentArea(const FObjectInitializer& Initializer);
};

UCLASS()
class GAMEASTRAFOREST_API UTempleBlueDeploymentArea : public UNavArea
{
    GENERATED_BODY()
public:
    explicit UTempleBlueDeploymentArea(const FObjectInitializer& Initializer);
};

UCLASS(Abstract)
class GAMEASTRAFOREST_API UTempleDeploymentRouteFilter : public UNavigationQueryFilter
{
    GENERATED_BODY()
protected:
    virtual void InitializeFilter(const ANavigationData& NavData, const UObject* Querier, FNavigationQueryFilter& Filter) const override;
};

UCLASS()
class GAMEASTRAFOREST_API UTempleRedRouteFilter : public UTempleDeploymentRouteFilter
{
    GENERATED_BODY()
public:
    explicit UTempleRedRouteFilter(const FObjectInitializer& Initializer);
};

UCLASS()
class GAMEASTRAFOREST_API UTempleBlueRouteFilter : public UTempleDeploymentRouteFilter
{
    GENERATED_BODY()
public:
    explicit UTempleBlueRouteFilter(const FObjectInitializer& Initializer);
};

/** Paints an upright cylinder of existing walkable floor, centered on a team's player starts. */
UCLASS()
class GAMEASTRAFOREST_API ATempleDeploymentNavigation : public ANavModifierVolume
{
    GENERATED_BODY()
public:
    explicit ATempleDeploymentNavigation(const FObjectInitializer& Initializer);
    virtual void GetNavigationData(FNavigationRelevantData& Data) const override;
    virtual FBox GetNavigationBounds() const override;
};
