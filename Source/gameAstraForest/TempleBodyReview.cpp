#if !UE_BUILD_SHIPPING
#include "TempleFighter.h"
#include "TempleMatch.h"
#include "Animation/AnimInstance.h"
#include "Animation/AnimMontage.h"
#include "Camera/CameraActor.h"
#include "Camera/CameraComponent.h"
#include "Camera/PlayerCameraManager.h"
#include "Components/SkeletalMeshComponent.h"
#include "Engine/SkeletalMesh.h"
#include "EngineUtils.h"
#include "HAL/FileManager.h"
#include "HAL/PlatformMisc.h"
#include "Misc/CommandLine.h"
#include "Misc/Paths.h"
#include "UnrealClient.h"

namespace
{
struct FBodyPlaybackReview
{
    FString Directory;
    FName Identity;
    TWeakObjectPtr<ATempleFighter> Subject;
    TWeakObjectPtr<ACameraActor> Camera;
    FVector Previous=FVector::ZeroVector;
    float Start=-1, ReloadAt=-1, Distance=0, LastSample=0, FootMin=MAX_FLT, FootMax=-MAX_FLT;
    int32 TeamOverride=-1, RoutePhotos=0;
    float LastRoutePhoto=0.f;
    float SubjectSince=0.f;
    uint64 FirstFrame=0;
    bool bTour=false;
    bool bFirst=false, bSecond=false, bShot=false, bReload=false, bPortrait=false;
    FBodyPlaybackReview()
    {
        if (FParse::Value(FCommandLine::Get(),TEXT("TempleBodyReview="),Directory))
        {
            Directory=FPaths::ConvertRelativePathToFull(Directory);
            IFileManager::Get().MakeDirectory(*Directory,true);
            FParse::Value(FCommandLine::Get(),TEXT("TempleBodyTeam="),TeamOverride);
            FString RequestedIdentity;
            if (FParse::Value(FCommandLine::Get(),TEXT("TempleBodyIdentity="),RequestedIdentity))
                Identity=FName(*RequestedIdentity);
            bTour=FParse::Param(FCommandLine::Get(),TEXT("TempleBodyTour"));
        }
    }
    void Photo(const TCHAR* Label)
    {
        FScreenshotRequest::RequestScreenshot(FPaths::Combine(Directory,FString(Label)+TEXT(".png")),false,false);
    }
    void Follow(ATempleFighter* Fighter, APlayerController* Viewer)
    {
        const FVector Centre=Fighter->GetActorLocation()-FVector(0,0,3);
        const FVector Forward=Fighter->GetActorForwardVector(),Right=Fighter->GetActorRightVector();
        FCollisionQueryParams Query(SCENE_QUERY_STAT(TempleReviewCamera),false,Fighter);
        FVector Best=Centre;
        float BestScore=-1;
        for (const float Angle : {52.f,-52.f,0.f,85.f,-85.f,135.f,-135.f,180.f})
        {
            const float Radians=FMath::DegreesToRadians(Angle);
            const FVector Wanted=Centre+(Forward*FMath::Cos(Radians)+Right*FMath::Sin(Radians))*415+FVector(0,0,45);
            FHitResult Block;
            const bool Hit=Fighter->GetWorld()->SweepSingleByChannel(Block,Centre,Wanted,FQuat::Identity,
                ECC_Visibility,FCollisionShape::MakeSphere(11),Query);
            const FVector Free=Hit?Block.Location:Wanted;
            const float Score=FVector::Dist2D(Centre,Free)+22.f*FMath::Cos(Radians+FMath::DegreesToRadians(35.f));
            if (Score>BestScore) { Best=Free; BestScore=Score; }
        }
        const FRotator Rotation=(Centre-Best).Rotation();
        if (Viewer->PlayerCameraManager && (FVector::DistSquared(Camera->GetActorLocation(),Best)>FMath::Square(80.f)
            || Camera->GetActorQuat().AngularDistance(Rotation.Quaternion())>FMath::DegreesToRadians(15.f)))
            Viewer->PlayerCameraManager->SetGameCameraCutThisFrame();
        Camera->SetActorLocationAndRotation(Best,Rotation);
        const float Framing=2.f*FMath::RadiansToDegrees(FMath::Atan2(205.f,FVector::Distance(Best,Centre)));
        Camera->GetCameraComponent()->SetFieldOfView(FMath::Clamp(Framing,54.f,108.f));
    }
    void Tick(ATempleFighter* Viewer)
    {
        if (Directory.IsEmpty() || !Viewer->IsPlayerControlled() || !Viewer->IsLocallyControlled()) return;
        UWorld* World=Viewer->GetWorld();
        auto* State=World->GetGameState<ATempleGameState>();
        auto* PC=Cast<APlayerController>(Viewer->GetController());
        if (!State || !PC || !World->IsGameWorld()) return;
        const float Now=World->GetTimeSeconds();
        if (Start>0 && (Now-Start>(bTour?32.f:18.f) || State->Phase==3 || (!bTour && bReload && (Identity.IsNone() || (bFirst && bSecond)))))
        {
            if (!FScreenshotRequest::IsScreenshotRequested())
            {
                UE_LOG(LogTemp,Display,TEXT("TempleBody complete distanceCm=%.1f footSeparationRange=(%.1f %.1f) strideA=%d strideB=%d shot=%d reload=%d"),
                    Distance,FootMin,FootMax,bFirst,bSecond,bShot,bReload);
                FPlatformMisc::RequestExit(false);
            }
            return;
        }
        if (State->Phase!=2) return;
        if (!Camera.IsValid())
        {
            auto* Actor=World->SpawnActor<ACameraActor>();
            Actor->GetCameraComponent()->SetFieldOfView(58.f);
            Camera=Actor;
            PC->SetViewTarget(Actor);
        }
        if (!Subject.IsValid() || !Subject->IsAlive())
        {
            const int32 Team=TeamOverride==0 || TeamOverride==1?TeamOverride:Viewer->GetTeam();
            for (TActorIterator<ATempleFighter> It(World);It;++It)
                if (*It!=Viewer && It->IsAlive() && !It->IsPlayerControlled()
                    && (Identity.IsNone() ? It->GetTeam()==Team : It->GetBotAppearanceName()==Identity && It->GetBotPresentationBody() && (TeamOverride<0 || It->GetTeam()==TeamOverride))
                    && It->GetVelocity().Size2D()>140.f)
                { Subject=*It; Previous=It->GetActorLocation(); SubjectSince=Now; FirstFrame=GFrameCounter; break; }
            if (!Subject.IsValid() || !Subject->IsAlive()) return;
            if (Start<0) Start=Now;
        }
        auto* Fighter=Subject.Get();
        Follow(Fighter,PC);
        Distance+=FVector::Dist2D(Previous,Fighter->GetActorLocation());
        Previous=Fighter->GetActorLocation();
        auto* Body=Fighter->GetBotPresentationBody();
        if (!Body && !Identity.IsNone()) return;
        if (!Body) Body=Fighter->GetMesh();
        const float Feet=FVector::DotProduct(Body->GetSocketLocation(TEXT("foot_l"))-Body->GetSocketLocation(TEXT("foot_r")),Fighter->GetActorForwardVector());
        FootMin=FMath::Min(FootMin,Feet); FootMax=FMath::Max(FootMax,Feet);
        if (Now>LastSample+.25f)
        {
            LastSample=Now;
            if (!Identity.IsNone())
            {
                auto ToeHeight = [&](const FName Toe)
                {
                    const FVector Position=Body->GetSocketLocation(Toe);
                    FCollisionQueryParams Query(SCENE_QUERY_STAT(TempleFootReview),false,Fighter);
                    FHitResult Ground;
                    if (!World->LineTraceSingleByChannel(Ground, Position+FVector(0,0,35),Position-FVector(0,0,120),ECC_Visibility,Query))
                        return -999.f;
                    return static_cast<float>(Position.Z-Ground.ImpactPoint.Z);
                };
                UE_LOG(LogTemp,Display,TEXT("TempleBody contact identity=%s leftToeCm=%.1f rightToeCm=%.1f rightHandToDriverCm=%.1f"),
                    *Identity.ToString(),ToeHeight(TEXT("ball_l")),ToeHeight(TEXT("ball_r")),
                    FVector::Distance(Body->GetSocketLocation(TEXT("hand_r")),Fighter->GetMesh()->GetSocketLocation(TEXT("hand_r"))));
            }
            UE_LOG(LogTemp,Display,TEXT("TempleBody sample team=%d identity=%s mesh=%s travel=%.1f speed=%.1f footDifference=%.1f body=%s slot=%s reload=%.2f"),
                Fighter->GetTeam(),*Fighter->GetBotAppearanceName().ToString(),*GetNameSafe(Body->GetSkeletalMeshAsset()),Distance,Fighter->GetVelocity().Size2D(),Feet,*GetNameSafe(Body->GetAnimInstance()),
                *GetNameSafe(Body->GetAnimInstance()?Body->GetAnimInstance()->GetCurrentActiveMontage():nullptr),Fighter->GetReloadAlpha());
        }
        if (FScreenshotRequest::IsScreenshotRequested()) return;
        if (!Identity.IsNone() && (Now-SubjectSince<2.f || GFrameCounter-FirstFrame<45)) return;
        if (bTour)
        {
            if (Now-LastRoutePhoto>2.f)
            {
                LastRoutePhoto=Now;
                Photo(*FString::Printf(TEXT("Match%02d"),++RoutePhotos));
            }
            return;
        }
        if (!Identity.IsNone() && !bPortrait && Distance>15.f) { Photo(TEXT("InMatch")); bPortrait=true; return; }
        if (!bFirst && Distance>110 && Feet>7) { Photo(TEXT("StrideLeft")); bFirst=true; return; }
        if (!bSecond && bFirst && Feet<-7) { Photo(TEXT("StrideRight")); bSecond=true; return; }
        if (!Identity.IsNone() && bSecond && RoutePhotos<5 && Now-LastRoutePhoto>.8f && Fighter->GetVelocity().Size2D()>200.f)
        {
            LastRoutePhoto=Now;
            Photo(*FString::Printf(TEXT("OnRoute%02d"),++RoutePhotos));
            return;
        }
        if (Now-Start>3.f && !bShot && !Fighter->IsReloading())
        {
            Fighter->SetTriggerHeld(true);
            const float Age=Now-Fighter->GetLocalShotTime();
            if (Age>.012f && Age<.055f) { Photo(TEXT("ThirdPersonFire")); bShot=true; }
            return;
        }
        if (bShot && ReloadAt<0)
        {
            Fighter->SetTriggerHeld(false);
            Fighter->StartReload();
            if (Fighter->IsReloading()) ReloadAt=Now;
        }
        if (!bReload && ReloadAt>0 && Fighter->GetReloadAlpha()>.42f)
        { Photo(TEXT("ThirdPersonReload")); bReload=true; }
    }
};
}
void UpdateTempleBodyReview(ATempleFighter* Fighter)
{
    static FBodyPlaybackReview Review;
    Review.Tick(Fighter);
}
#endif
