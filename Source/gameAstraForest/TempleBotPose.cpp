#include "TempleBotPose.h"
#include "Animation/AnimInstanceProxy.h"
#include "Components/CapsuleComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/World.h"
#include "GameFramework/Character.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "TwoBoneIK.h"

namespace
{
struct FTempleLimb
{
    int32 Upper, Middle, End;
    enum class ERole { Foot, WeaponHand, SupportHand } Role;
    double LengthRatio;
    int32 Ball = INDEX_NONE;
    FVector HeelLocal = FVector::ZeroVector, BallSoleLocal = FVector::ZeroVector, ToeLocal = FVector::ZeroVector;
    FVector GroundOffset = FVector::ZeroVector;
    double Lift = 0.0;
};

TArray<FTransform> ComponentBindPose(const FReferenceSkeleton& Skeleton)
{
    TArray<FTransform> Pose = Skeleton.GetRefBonePose();
    for (int32 Index = 1; Index < Pose.Num(); ++Index)
        Pose[Index] *= Pose[Skeleton.GetParentIndex(Index)];
    return Pose;
}

double FootwearSoleHeight(USkeletalMeshComponent* Body)
{
    // The optimized outfits have a separate pair of shoes. Use its unpadded imported mesh
    // bounds in body space, including an authored offset from the barefoot ground plane.
    TArray<USkeletalMeshComponent*> Parts;
    Body->GetOwner()->GetComponents(Parts);
    for (const USkeletalMeshComponent* Part : Parts)
    {
        const USkeletalMesh* Mesh = Part->GetSkeletalMeshAsset();
        if (!Mesh || Part == Body) continue;
        const FTransform ToBody = Part->GetComponentTransform().GetRelativeTransform(Body->GetComponentTransform());
        const FBox Box = Mesh->GetImportedBounds().TransformBy(ToBody).GetBox();
        if (Box.Max.Z < 40 && Box.Min.Z > -8 && Box.Min.Z < 6)
            return Box.Min.Z;
    }
    return 0.0;
}

class FTempleBotPoseProxy final : public FAnimInstanceProxy
{
public:
    explicit FTempleBotPoseProxy(UAnimInstance* Instance) : FAnimInstanceProxy(Instance) {}

    virtual void PreUpdate(UAnimInstance* Instance, float DeltaSeconds) override
    {
        FAnimInstanceProxy::PreUpdate(Instance, DeltaSeconds);
        const UTempleBotPose* Anim = CastChecked<UTempleBotPose>(Instance);
        const USkeletalMeshComponent* Source = Anim->Source.Get();
        USkeletalMesh* NewSource = Source ? Source->GetSkeletalMeshAsset() : nullptr;
        USkeletalMeshComponent* Target = Instance->GetSkelMeshComponent();
        USkeletalMesh* NewTarget = Target->GetSkeletalMeshAsset();
        bCopyFace = Anim->bCopyFacePose;
        if (!NewSource || !NewTarget)
        {
            SourcePose.Reset();
            return;
        }
        if (SourceAsset.Get() != NewSource || TargetAsset.Get() != NewTarget)
        {
            SourceAsset = NewSource;
            TargetAsset = NewTarget;
            BuildMapping(NewSource->GetRefSkeleton(), NewTarget->GetRefSkeleton(), bCopyFace ? 0.0 : FootwearSoleHeight(Target));
        }
        SourcePose = Source->GetComponentSpaceTransforms();
        if (!bCopyFace)
            SampleGround(Cast<ACharacter>(Source->GetOwner()), Target->GetComponentTransform(), DeltaSeconds);
    }

    virtual bool Evaluate(FPoseContext& Output) override
    {
        Output.Pose.ResetToRefPose();
        if (SourcePose.IsEmpty()) return true;
        const FBoneContainer& Bones = Output.Pose.GetBoneContainer();
        ComponentPose.SetNumUninitialized(Output.Pose.GetNumBones());
        for (const FCompactPoseBoneIndex Compact : Output.Pose.ForEachBoneIndex())
        {
            const int32 Index = Compact.GetInt();
            const int32 Target = Bones.MakeMeshPoseIndex(Compact).GetInt();
            const int32 Parent = Bones.GetParentBoneIndex(Compact).GetInt();
            const FTransform ParentCS = Parent == INDEX_NONE ? FTransform::Identity : ComponentPose[Parent];
            FTransform& Local = Output.Pose[Compact];
            FTransform CS = Local * ParentCS;
            const int32 Source = SourceForTarget[Target];
            if (SourcePose.IsValidIndex(Source))
            {
                if (bCopyFace)
                {
                    // The independently skinned face shares the assembled body's neck joints.
                    // Facial-only joints keep their local bind pose and continue to follow the head.
                    CS = SourcePose[Source];
                }
                else
                {
                    const FQuat Motion = SourcePose[Source].GetRotation() * SourceBind[Source].GetRotation().Inverse();
                    CS.SetRotation((Motion * TargetBind[Target].GetRotation()).GetNormalized());
                    if (Parent == INDEX_NONE || Target == Pelvis)
                        CS.SetTranslation(TargetBind[Target].GetTranslation() +
                            (SourcePose[Source].GetTranslation() - SourceBind[Source].GetTranslation()) * HeightRatio);
                }
                Local = CS.GetRelativeTransform(ParentCS);
            }
            ComponentPose[Index] = CS;
        }
        if (!bCopyFace)
        {
            FVector GripOffset = FVector::ZeroVector;
            for (const FTempleLimb& Limb : Limbs) PlaceLimb(Output, Limb, GripOffset);
        }
        return true;
    }

private:
    void BuildMapping(const FReferenceSkeleton& Source, const FReferenceSkeleton& Target, double SoleZ)
    {
        SourceBind = ComponentBindPose(Source);
        TargetBind = ComponentBindPose(Target);
        SourceForTarget.SetNum(Target.GetNum());
        for (int32 Index = 0; Index < Target.GetNum(); ++Index)
            SourceForTarget[Index] = Source.FindBoneIndex(Target.GetBoneName(Index));
        Pelvis = Target.FindBoneIndex(TEXT("pelvis"));
        const int32 SourcePelvis = Source.FindBoneIndex(TEXT("pelvis"));
        HeightRatio = TargetBind.IsValidIndex(Pelvis) && SourceBind.IsValidIndex(SourcePelvis) &&
            SourceBind[SourcePelvis].GetTranslation().Z > 1.0 ?
            TargetBind[Pelvis].GetTranslation().Z / SourceBind[SourcePelvis].GetTranslation().Z : 1.0;
        Limbs.Reset();
        auto AddLimb = [&](FName Upper, FName Middle, FName End, FTempleLimb::ERole Role, FName Ball = NAME_None)
        {
            FTempleLimb Limb{Target.FindBoneIndex(Upper), Target.FindBoneIndex(Middle), Target.FindBoneIndex(End), Role, 1.0};
            if (Limb.Upper != INDEX_NONE && Limb.Middle != INDEX_NONE && Limb.End != INDEX_NONE &&
                SourceForTarget[Limb.Upper] != INDEX_NONE && SourceForTarget[Limb.Middle] != INDEX_NONE &&
                SourceForTarget[Limb.End] != INDEX_NONE && Target.GetParentIndex(Limb.End) == Limb.Middle &&
                Target.GetParentIndex(Limb.Middle) == Limb.Upper)
            {
                const double SourceLength = Source.GetRefBonePose()[SourceForTarget[Limb.Middle]].GetTranslation().Size()
                    + Source.GetRefBonePose()[SourceForTarget[Limb.End]].GetTranslation().Size();
                const double TargetLength = Target.GetRefBonePose()[Limb.Middle].GetTranslation().Size()
                    + Target.GetRefBonePose()[Limb.End].GetTranslation().Size();
                if (SourceLength > UE_SMALL_NUMBER) Limb.LengthRatio = TargetLength / SourceLength;
                Limb.Ball = Target.FindBoneIndex(Ball);
                if (Limb.Ball != INDEX_NONE && SourceForTarget[Limb.Ball] != INDEX_NONE)
                {
                    const FTransform& AnkleRef = TargetBind[Limb.End];
                    const FTransform& BallRef = TargetBind[Limb.Ball];
                    FVector Forefoot = BallRef.GetLocation() - AnkleRef.GetLocation();
                    Forefoot.Z = 0.0;
                    FVector Heel = AnkleRef.GetLocation() - Forefoot * .35;
                    FVector BallSole = BallRef.GetLocation();
                    FVector Toe = BallSole + Forefoot * .40;
                    Heel.Z = BallSole.Z = Toe.Z = SoleZ;
                    Limb.HeelLocal = AnkleRef.InverseTransformPosition(Heel);
                    Limb.BallSoleLocal = BallRef.InverseTransformPosition(BallSole);
                    Limb.ToeLocal = BallRef.InverseTransformPosition(Toe);
                }
                Limbs.Add(Limb);
            }
        };
        AddLimb(TEXT("thigh_l"), TEXT("calf_l"), TEXT("foot_l"), FTempleLimb::ERole::Foot, TEXT("ball_l"));
        AddLimb(TEXT("thigh_r"), TEXT("calf_r"), TEXT("foot_r"), FTempleLimb::ERole::Foot, TEXT("ball_r"));
        AddLimb(TEXT("upperarm_r"), TEXT("lowerarm_r"), TEXT("hand_r"), FTempleLimb::ERole::WeaponHand);
        AddLimb(TEXT("upperarm_l"), TEXT("lowerarm_l"), TEXT("hand_l"), FTempleLimb::ERole::SupportHand);
    }

    FVector RetargetLegPoint(int32 TargetIndex) const
    {
        const int32 Driver = SourceForTarget[TargetIndex];
        return TargetBind[TargetIndex].GetLocation() +
            (SourcePose[Driver].GetLocation() - SourceBind[Driver].GetLocation()) * HeightRatio;
    }

    FQuat RetargetRotation(int32 TargetIndex) const
    {
        const int32 Driver = SourceForTarget[TargetIndex];
        return (SourcePose[Driver].GetRotation() * SourceBind[Driver].GetRotation().Inverse() *
            TargetBind[TargetIndex].GetRotation()).GetNormalized();
    }

    void SampleGround(ACharacter* Character, const FTransform& ToWorld, float DeltaSeconds)
    {
        const UCharacterMovementComponent* Move = Character ? Character->GetCharacterMovement() : nullptr;
        const double FloorZ = Character ? Character->GetActorLocation().Z -
            Character->GetCapsuleComponent()->GetScaledCapsuleHalfHeight() : 0.0;
        FCollisionObjectQueryParams Surfaces;
        Surfaces.AddObjectTypesToQuery(ECC_WorldStatic);
        Surfaces.AddObjectTypesToQuery(ECC_WorldDynamic);
        FCollisionQueryParams Query(SCENE_QUERY_STAT(TempleBotSole), false, Character);
        for (FTempleLimb& Foot : Limbs)
        {
            if (Foot.Role != FTempleLimb::ERole::Foot) continue;
            if (!Move || !Move->IsMovingOnGround() || Foot.Ball == INDEX_NONE ||
                !SourcePose.IsValidIndex(SourceForTarget[Foot.End]) || !SourcePose.IsValidIndex(SourceForTarget[Foot.Ball]))
            {
                Foot.Lift = 0.0;
                Foot.GroundOffset = FVector::ZeroVector;
                continue;
            }
            // Predict this frame's uncorrected ankle and toe flex. Sampling the already
            // corrected pose from the last frame produces oscillation on staircase edges.
            const FTransform Ankle(RetargetRotation(Foot.End), RetargetLegPoint(Foot.End));
            const FVector BallInFoot = TargetBind[Foot.End].InverseTransformPosition(TargetBind[Foot.Ball].GetLocation());
            const FTransform Ball(RetargetRotation(Foot.Ball), Ankle.TransformPosition(BallInFoot));
            const double MaxLift = FMath::Min<double>(Move->MaxStepHeight, 35.0);
            double Needed = 0.0;
            for (const FVector& P : {Ankle.TransformPosition(Foot.HeelLocal), Ball.TransformPosition(Foot.BallSoleLocal),
                                     Ball.TransformPosition(Foot.ToeLocal)})
            {
                const FVector Sole = ToWorld.TransformPosition(P);
                const double Top = FloorZ + Move->MaxStepHeight + 1.0;
                if (Sole.Z >= Top) continue;
                FHitResult Hit;
                const FVector Start(Sole.X, Sole.Y, Top);
                if (Character->GetWorld()->LineTraceSingleByObjectType(Hit, Start,
                        FVector(Sole.X, Sole.Y, Sole.Z - 1.0), Surfaces, Query) &&
                    !Hit.bStartPenetrating && Hit.GetComponent() && Move->IsWalkable(Hit) &&
                    Hit.GetComponent()->GetCollisionResponseToChannel(ECC_Pawn) == ECR_Block &&
                    Hit.GetComponent()->CanCharacterStepUp(Character))
                    Needed = FMath::Max(Needed, Hit.ImpactPoint.Z - Sole.Z);
            }
            // Clear solid terrain immediately, then release within a short part of the
            // swing phase. There is no downward pull on a foot already clear of the floor.
            Foot.Lift = FMath::Max(FMath::Clamp(Needed, 0.0, MaxLift), Foot.Lift - 360.0 * DeltaSeconds);
            Foot.GroundOffset = ToWorld.InverseTransformVector(FVector(0,0,Foot.Lift));
        }
    }

    void PlaceLimb(FPoseContext& Output, const FTempleLimb& Limb, FVector& GripOffset)
    {
        const FBoneContainer& Bones = Output.Pose.GetBoneContainer();
        const FCompactPoseBoneIndex Upper = Bones.MakeCompactPoseIndex(FMeshPoseBoneIndex(Limb.Upper));
        const FCompactPoseBoneIndex Middle = Bones.MakeCompactPoseIndex(FMeshPoseBoneIndex(Limb.Middle));
        const FCompactPoseBoneIndex End = Bones.MakeCompactPoseIndex(FMeshPoseBoneIndex(Limb.End));
        if (!Upper.IsValid() || !Middle.IsValid() || !End.IsValid()) return;
        const int32 SourceEnd = SourceForTarget[Limb.End];
        const int32 SourceMiddle = SourceForTarget[Limb.Middle];
        if (!SourcePose.IsValidIndex(SourceEnd) || !SourcePose.IsValidIndex(SourceMiddle)) return;
        FTransform& UpperCS = ComponentPose[Upper.GetInt()];
        FTransform& MiddleCS = ComponentPose[Middle.GetInt()];
        FTransform& EndCS = ComponentPose[End.GetInt()];
        FVector Goal = SourcePose[SourceEnd].GetTranslation();
        FVector Pole = SourcePose[SourceMiddle].GetTranslation();
        if (Limb.Role == FTempleLimb::ERole::Foot)
        {
            // Place the sole on the same ground plane while retaining the character's ankle height.
            Goal = RetargetLegPoint(Limb.End) + Limb.GroundOffset;
            Pole = RetargetLegPoint(Limb.Middle) + Limb.GroundOffset * .5;
        }
        else
        {
            const FVector SourceShoulder = SourcePose[SourceForTarget[Limb.Upper]].GetTranslation();
            Pole = UpperCS.GetTranslation() + (Pole - SourceShoulder) * Limb.LengthRatio;
            if (Limb.Role == FTempleLimb::ERole::WeaponHand)
                Goal = UpperCS.GetTranslation() + (Goal - SourceShoulder) * Limb.LengthRatio;
            else
                // The rifle is rigid; retain the authored two-hand spacing and magazine travel.
                Goal += GripOffset;
        }
        AnimationCore::SolveTwoBoneIK(UpperCS, MiddleCS, EndCS, Pole, Goal, false, 1.0, 1.0);
        if (Limb.Role == FTempleLimb::ERole::WeaponHand)
            GripOffset = EndCS.GetTranslation() - SourcePose[SourceEnd].GetTranslation();
        Output.Pose[Upper] = UpperCS.GetRelativeTransform(ComponentPose[Bones.GetParentBoneIndex(Upper).GetInt()]);
        Output.Pose[Middle] = MiddleCS.GetRelativeTransform(UpperCS);
        Output.Pose[End] = EndCS.GetRelativeTransform(MiddleCS);
    }

    TWeakObjectPtr<USkeletalMesh> SourceAsset, TargetAsset;
    TArray<FTransform> SourceBind, TargetBind, SourcePose, ComponentPose;
    TArray<int32> SourceForTarget;
    TArray<FTempleLimb> Limbs;
    int32 Pelvis = INDEX_NONE;
    double HeightRatio = 1.0;
    bool bCopyFace = false;
};
}

void UTempleBotPose::SetSource(USkeletalMeshComponent* Mesh, bool bIsFace)
{
    Source = Mesh;
    bCopyFacePose = bIsFace;
}

FAnimInstanceProxy* UTempleBotPose::CreateAnimInstanceProxy() { return new FTempleBotPoseProxy(this); }
void UTempleBotPose::DestroyAnimInstanceProxy(FAnimInstanceProxy* Proxy) { delete static_cast<FTempleBotPoseProxy*>(Proxy); }
