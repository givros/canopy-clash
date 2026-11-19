#include "TempleRifleMesh.h"

void UTempleRifleMesh::UpdateBounds()
{
    Super::UpdateBounds();
    // Modular characters and held items must agree on visibility when emerging from cover.
    // Keep the rifle's own extent as well, since its tip can project beyond the character.
    if (GetAttachSocketName() == TEXT("hand_r"))
        if (const USceneComponent* Body = GetAttachParent())
            Bounds = Bounds + Body->Bounds;
}
