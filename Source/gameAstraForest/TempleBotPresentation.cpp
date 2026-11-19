#include "TempleFighter.h"
#include "TempleBotController.h"
#include "TempleBotPose.h"
#include "TempleMagazinePresentation.h"
#include "Components/ChildActorComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/AssetManager.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/StaticMesh.h"
#include "Engine/StreamableManager.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "PhysicsEngine/PhysicsAsset.h"
#include "PhysicsEngine/SkeletalBodySetup.h"
#include "UObject/ConstructorHelpers.h"

namespace
{
const FName Identities[] = {TEXT("Hannah"), TEXT("Kabir"), TEXT("Hero1"), TEXT("Advika"), TEXT("Dean")};
static_assert(UE_ARRAY_COUNT(Identities) == ATempleBotController::AppearanceCount);
constexpr uint8 NoBotAppearance = 255;

USkeletalMeshComponent* FindPart(const TArray<USkeletalMeshComponent*>& Parts, FName Name, FName Tag)
{
    for (USkeletalMeshComponent* Part : Parts)
        if (Part->GetSkeletalMeshAsset() && (Part->GetFName() == Name || Part->ComponentHasTag(Tag)))
            return Part;
    return nullptr;
}

void DrivePose(USkeletalMeshComponent* Part, USkeletalMeshComponent* Source, bool bIsFace)
{
    Part->SetLeaderPoseComponent(nullptr);
    Part->AddTickPrerequisiteComponent(Source);
    Part->SetAnimInstanceClass(UTempleBotPose::StaticClass());
    if (UTempleBotPose* Anim = Cast<UTempleBotPose>(Part->GetAnimInstance()))
        Anim->SetSource(Source, bIsFace);
}
}

void ATempleFighter::InitializeBotAppearances()
{
    BotPresentation = CreateDefaultSubobject<UChildActorComponent>(TEXT("BotPresentation"));
    BotPresentation->SetupAttachment(GetMesh());
    BotPresentation->SetCanEverAffectNavigation(false);
    static ConstructorHelpers::FObjectFinder<UStaticMesh> Band(TEXT("/Engine/BasicShapes/Cylinder.Cylinder"));
    static ConstructorHelpers::FObjectFinder<UMaterialInterface> Paint(TEXT("/Engine/BasicShapes/BasicShapeMaterial.BasicShapeMaterial"));
    BotArmbandMesh = Band.Object;
    BotArmbandMaterial = Paint.Object;
    for (FName Identity : Identities)
    {
        const FString Name = Identity.ToString();
        BotAppearanceClasses.Emplace(FSoftObjectPath(FString::Printf(
            TEXT("/Game/TempleTDM/Bots/%s/BP_%s.BP_%s_C"), *Name, *Name, *Name)));
    }
}

FName ATempleFighter::GetBotAppearanceName() const
{
    return BotAppearance < UE_ARRAY_COUNT(Identities) ? Identities[BotAppearance] : NAME_None;
}

int32 ATempleFighter::FindBotAppearanceSlot(FName Identity)
{
    return MakeArrayView(Identities).IndexOfByKey(Identity);
}

void ATempleFighter::SelectBotAppearance(AController* NewController)
{
    if (!HasAuthority()) return;
    uint8 NewAppearance = NoBotAppearance;
    if (const ATempleBotController* Bot = Cast<ATempleBotController>(NewController))
        NewAppearance = Bot->GetAppearanceSlot();
    if (BotAppearance == NewAppearance) return;
    BotAppearance = NewAppearance;
    OnRep_BotAppearance();
    ForceNetUpdate();
}

void ATempleFighter::CancelBotAppearanceLoad()
{
    if (BotAppearanceLoad)
    {
        BotAppearanceLoad->CancelHandle();
        BotAppearanceLoad.Reset();
    }
}

void ATempleFighter::OnRep_BotAppearance()
{
    if (GetNetMode() == NM_DedicatedServer) return;
    CancelBotAppearanceLoad();
    if (BotPresentationBody) AttachBotRifle(nullptr);
    BotPresentationBody = nullptr;
    BotArmbandPaint = nullptr;
    BotPresentation->SetChildActorClass(nullptr);
    BotPresentation->SetRelativeTransform(FTransform::Identity);
    GetMesh()->SetVisibility(true, false);
    GetMesh()->SetCastHiddenShadow(true);
    if (!BotAppearanceClasses.IsValidIndex(BotAppearance) || BotAppearanceClasses[BotAppearance].IsNull()) return;
    if (BotAppearanceClasses[BotAppearance].Get())
    {
        FinishBotAppearance();
        return;
    }
    BotAppearanceLoad = UAssetManager::GetStreamableManager().RequestAsyncLoad(
        BotAppearanceClasses[BotAppearance].ToSoftObjectPath(),
        FStreamableDelegate::CreateUObject(this, &ATempleFighter::FinishBotAppearance));
}

void ATempleFighter::FinishBotAppearance()
{
    if (IsActorBeingDestroyed() || !BotAppearanceClasses.IsValidIndex(BotAppearance)) return;
    UClass* PresentationClass = BotAppearanceClasses[BotAppearance].Get();
    if (!PresentationClass)
    {
        UE_LOG(LogTemp, Error, TEXT("Could not load bot appearance %s"), *BotAppearanceClasses[BotAppearance].ToString());
        return;
    }
    BotPresentation->SetChildActorClass(PresentationClass);
    AActor* Model = BotPresentation->GetChildActor();
    if (!Model) return;
    Model->SetActorEnableCollision(false);
    TArray<USkeletalMeshComponent*> Parts;
    Model->GetComponents(Parts, true);
    USkeletalMeshComponent* Body = FindPart(Parts, TEXT("Body"), TEXT("TempleBody"));
    if (!Body || Body->GetBoneIndex(TEXT("foot_l")) == INDEX_NONE || Body->GetBoneIndex(TEXT("foot_r")) == INDEX_NONE ||
        Body->GetBoneIndex(TEXT("hand_l")) == INDEX_NONE || Body->GetBoneIndex(TEXT("hand_r")) == INDEX_NONE)
    {
        UE_LOG(LogTemp, Error, TEXT("Bot appearance %s requires a Body skeletal mesh with both hands and feet"), *GetNameSafe(PresentationClass));
        BotPresentation->SetChildActorClass(nullptr);
        return;
    }

    // A presentation may have its own actor-facing yaw. Align the actual body mesh space,
    // including its authored root offset, with the existing fighter's mesh space.
    const FTransform BodyToPresentation = Body->GetComponentTransform().GetRelativeTransform(BotPresentation->GetComponentTransform());
    BotPresentation->SetRelativeTransform(BodyToPresentation.Inverse());
    Body->VisibilityBasedAnimTickOption = EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
    DrivePose(Body, GetMesh(), false);
    USkeletalMeshComponent* Face = FindPart(Parts, TEXT("Face"), TEXT("TempleFace"));
    // The face, hair and brows must not be occluded independently of the body between
    // successive frames of locomotion. Leave some space above the authored body for hair.
    if (Face && Face->GetAttachParent() == Body)
    {
        Body->SetBoundsScale(FMath::Max(Body->BoundsScale, 1.2f));
        Face->bUseAttachParentBound = true;
        Face->UpdateBounds();
    }
    TArray<UPrimitiveComponent*> Primitives;
    Model->GetComponents(Primitives, true);
    for (UPrimitiveComponent* Prim : Primitives)
    {
        Prim->SetCanEverAffectNavigation(false);
        Prim->SetGenerateOverlapEvents(false);
        if (Face && Prim->GetAttachParent() == Face)
        {
            Prim->bUseAttachParentBound = true;
            Prim->UpdateBounds();
        }
        if (Prim == Body) continue;
        if (USkinnedMeshComponent* Skinned = Cast<USkinnedMeshComponent>(Prim))
        {
            Skinned->AddTickPrerequisiteComponent(Body);
            if (Face && Skinned == Face)
            {
                if (!Face->GetAnimClass()) DrivePose(Face, Body, true);
            }
            else if (USkeletalMeshComponent* Garment = Cast<USkeletalMeshComponent>(Skinned); !Garment || !Garment->GetAnimClass())
            {
                Skinned->SetLeaderPoseComponent(Body);
            }
        }
    }
    BotPresentationBody = Body;
    AttachBotRifle(Body);
    AttachBotArmband(Model, Body);
    OnRep_Team();
    GetMesh()->SetCastHiddenShadow(false);
    GetMesh()->SetVisibility(false, false);
    UE_LOG(LogTemp, Display, TEXT("Bot appearance %s attached to %s"), *GetBotAppearanceName().ToString(), *GetName());
}

void ATempleFighter::AttachBotRifle(USkeletalMeshComponent* Body)
{
    const FName Grip = TEXT("HandGrip_R");
    if (!Body)
    {
        WorldRifle->AttachToComponent(GetMesh(), FAttachmentTransformRules::SnapToTargetIncludingScale, Grip);
        WorldRifle->SetRelativeTransform(AuthoredWorldRifleOffset);
        WorldMagazine->SetHandRig(GetMesh());
        return;
    }
    AuthoredWorldRifleOffset = WorldRifle->GetRelativeTransform();
    const FName Right = TEXT("hand_r");
    const FName Left = TEXT("hand_l");
    const FReferenceSkeleton& Driver = GetMesh()->GetSkeletalMeshAsset()->GetRefSkeleton();
    const FReferenceSkeleton& Target = Body->GetSkeletalMeshAsset()->GetRefSkeleton();
    auto SourceBasisInTarget = [&](FName Hand)
    {
        const FQuat DriverRest = Driver.GetBoneAbsoluteTransform(Driver.FindBoneIndex(Hand)).GetRotation();
        const FQuat TargetRest = Target.GetBoneAbsoluteTransform(Target.FindBoneIndex(Hand)).GetRotation();
        return (TargetRest.Inverse() * DriverRest).GetNormalized();
    };
    const FTransform Hand = GetMesh()->GetSocketTransform(Right, RTS_Component);
    const FTransform SourceGrip = GetMesh()->GetSocketTransform(Grip, RTS_Component).GetRelativeTransform(Hand);
    const FTransform GripInTarget = SourceGrip * FTransform(SourceBasisInTarget(Right));
    WorldRifle->AttachToComponent(Body, FAttachmentTransformRules::SnapToTargetIncludingScale, Right);
    WorldRifle->SetRelativeTransform(AuthoredWorldRifleOffset * GripInTarget);
    WorldMagazine->SetHandRig(Body, SourceBasisInTarget(Left));
}

void ATempleFighter::AttachBotArmband(AActor* Model, USkeletalMeshComponent* Body)
{
    const FName UpperArm(TEXT("upperarm_l"));
    const FReferenceSkeleton& Skeleton = Body->GetSkeletalMeshAsset()->GetRefSkeleton();
    const int32 Shoulder = Skeleton.FindBoneIndex(UpperArm);
    const int32 Elbow = Skeleton.FindBoneIndex(TEXT("lowerarm_l"));
    if (!BotArmbandMesh || !BotArmbandMaterial || Shoulder == INDEX_NONE || Elbow == INDEX_NONE ||
        Skeleton.GetParentIndex(Elbow) != Shoulder) return;
    const FVector Segment = Skeleton.GetRefBonePose()[Elbow].GetTranslation();
    const FVector Axis = Segment.GetSafeNormal();
    if (Axis.IsNearlyZero()) return;

    FVector Center = Segment * 0.46;
    double Radius = Segment.Size() * 0.19;
    if (const UPhysicsAsset* Physics = Body->GetPhysicsAsset())
    {
        const int32 BodyIndex = Physics->FindBodyIndex(UpperArm);
        if (Physics->SkeletalBodySetups.IsValidIndex(BodyIndex))
        {
            const USkeletalBodySetup* Setup = Physics->SkeletalBodySetups[BodyIndex];
            if (Setup && !Setup->AggGeom.SphylElems.IsEmpty())
            {
                const FKSphylElem& Arm = Setup->AggGeom.SphylElems[0];
                Radius = FMath::Clamp<double>(Arm.Radius, Segment.Size() * .16, Segment.Size() * .24);
                Center += FVector::VectorPlaneProject(Arm.Center, Axis);
            }
        }
    }
    // Leave room for the shirt sleeve, including Hero's tailored jacket.
    Radius += GetBotAppearanceName() == TEXT("Hero1") ? 1.4 : 0.8;
    const double Width = Segment.Size() * .23;
    const FVector Extent = BotArmbandMesh->GetBounds().BoxExtent;
    if (Extent.GetMin() <= 0) return;
    UStaticMeshComponent* Band = NewObject<UStaticMeshComponent>(Model, TEXT("TeamArmband"), RF_Transient);
    Model->AddInstanceComponent(Band);
    Band->SetupAttachment(Body, UpperArm);
    Band->SetStaticMesh(BotArmbandMesh);
    Band->SetCanEverAffectNavigation(false);
    Band->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    Band->SetGenerateOverlapEvents(false);
    Band->SetRelativeTransform(FTransform(FQuat::FindBetweenNormals(FVector::UpVector, Axis), Center,
        FVector(Radius / Extent.X, Radius / Extent.Y, Width / (2 * Extent.Z))));
    BotArmbandPaint = UMaterialInstanceDynamic::Create(BotArmbandMaterial, Band);
    Band->SetMaterial(0, BotArmbandPaint);
    Band->RegisterComponent();
}
