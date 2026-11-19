#pragma once

#include "Components/SkeletalMeshComponent.h"
#include "TempleRifleMesh.generated.h"

UCLASS()
class UTempleRifleMesh : public USkeletalMeshComponent
{
    GENERATED_BODY()
public:
    virtual void UpdateBounds() override;
};
