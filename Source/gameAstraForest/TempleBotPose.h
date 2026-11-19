#pragma once

#include "Animation/AnimInstance.h"
#include "TempleBotPose.generated.h"

class USkeletalMeshComponent;

/** Drives an assembled MetaHuman from the authoritative fighter mesh, preserving its own bind pose. */
UCLASS(Transient)
class UTempleBotPose : public UAnimInstance
{
    GENERATED_BODY()
public:
    void SetSource(USkeletalMeshComponent* Mesh, bool bIsFace);
    TWeakObjectPtr<USkeletalMeshComponent> Source;
    bool bCopyFacePose = false;
protected:
    virtual FAnimInstanceProxy* CreateAnimInstanceProxy() override;
    virtual void DestroyAnimInstanceProxy(FAnimInstanceProxy* Proxy) override;
};
