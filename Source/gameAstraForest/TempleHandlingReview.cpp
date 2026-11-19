#if !UE_BUILD_SHIPPING
#include "TempleFighter.h"
#include "TempleMatch.h"
#include "Camera/CameraComponent.h"
#include "Components/CapsuleComponent.h"
#include "Engine/GameViewportClient.h"
#include "EngineUtils.h"
#include "AIController.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/InputDeviceLibrary.h"
#include "HAL/PlatformMisc.h"
#include "InputKeyEventArgs.h"
#include "Misc/CommandLine.h"
#include "Misc/Paths.h"
#include "UnrealClient.h"

namespace TempleHandling
{
struct FBindingCase
{
    FKey Key;
    FVector2D Direction;
    FKey Modifier;
    float ExpectedSpeed;
    const TCHAR* Label;
};
const FBindingCase Cases[]={
    {EKeys::W,{1,0},{},510,TEXT("W")},{EKeys::Z,{1,0},{},510,TEXT("Z")},
    {EKeys::Q,{0,-1},{},510,TEXT("Q")},{EKeys::A,{0,-1},{},510,TEXT("A")},
    {EKeys::S,{-1,0},{},510,TEXT("S")},{EKeys::D,{0,1},{},510,TEXT("D")},
    {EKeys::Up,{1,0},{},510,TEXT("Up")},{EKeys::Down,{-1,0},{},510,TEXT("Down")},
    {EKeys::Left,{0,-1},{},510,TEXT("Left")},{EKeys::Right,{0,1},{},510,TEXT("Right")},
    {EKeys::W,{1,0},EKeys::LeftShift,690,TEXT("Sprint")},
    {EKeys::W,{1,0},EKeys::LeftControl,235,TEXT("Crouch")},
    {EKeys::W,{1,0},EKeys::RightMouseButton,325,TEXT("ADS")}};
FDelegateHandle Tick;
enum class EStage {Countdown,Settle,BeginMove,Moving,Braking,Jump,Airborne,Look,Looking,ADS,Zooming,Returning,Shot,Firing,Release,Reload,Loading,ApproachCover,AtCover,Impact,Done};
EStage Stage=EStage::Countdown;
int32 Index=0,Failures=0,AmmoAtRelease=0;
float Due=0,Started=0,StandingEye=0,JumpPeak=0,AmmoBefore=0,FovAtStart=0,FovAtMiddle=0;
FVector Origin;
TWeakObjectPtr<ATempleFighter> CoverTarget;
float CoverTargetHealth=0;
FString HandlingPictures;
void Check(const TCHAR* Label,bool Pass,float Value=0,float Second=0)
{
    if(!Pass)++Failures;
    UE_LOG(LogTemp,Display,TEXT("TInput|check|%s|%d|%.3f|%.3f"),Label,int32(Pass),Value,Second);
}
void Key(ATemplePlayerController* PC,FKey Input,EInputEvent Event,float Amount=-1)
{
    if(!Input.IsValid())return;
    auto* Viewport=PC->GetWorld()->GetGameViewport();
    const FInputDeviceId Device=UInputDeviceLibrary::GetPrimaryInputDeviceForUser(PC->GetPlatformUserId());
    const float Value=(Amount==-1)?float(Event==IE_Pressed):Amount;
    Viewport->InputKey(FInputKeyEventArgs::CreateSimulated(Input,Event,Value,-1,Device,false,Viewport->Viewport));
}
void ResetPose(ATemplePlayerController* PC,ATempleFighter* F)
{
    // The temple hall provides a flat, unobstructed repeatable start for each input.
    F->TeleportTo(FVector(8050,0,2898),FRotator::ZeroRotator);
    F->GetCharacterMovement()->StopMovementImmediately();
    PC->SetControlRotation(FRotator::ZeroRotator);
}
void Frame(UWorld* World)
{
    if(!World || World->GetNetMode()!=NM_Standalone || !World->IsGameWorld() || !World->GetGameViewport())return;
    auto* PC=Cast<ATemplePlayerController>(World->GetFirstPlayerController());
    auto* F=PC?Cast<ATempleFighter>(PC->GetPawn()):nullptr;
    auto* S=World->GetGameState<ATempleGameState>();
    if(!F || !F->IsAlive() || !S)return;
    auto* Camera=F->FindComponentByClass<UCameraComponent>();
    if(!Camera)return;
    const float Now=World->GetTimeSeconds();
    if(Stage==EStage::Countdown)
    {
        if(S->Phase==1 && Started==0)
        {
            Started=Now;AmmoBefore=F->GetMagazineAmmo();Key(PC,EKeys::LeftMouseButton,IE_Pressed);
            Key(PC,EKeys::LeftMouseButton,IE_Released);
        }
        if(S->Phase!=2)return;
        Check(TEXT("countdown_ignores_fire"),Started>0 && F->GetMagazineAmmo()==AmmoBefore,F->GetMagazineAmmo());
        ResetPose(PC,F);Due=Now+.4f;Stage=EStage::Settle;return;
    }
    if(Stage==EStage::Airborne)
        JumpPeak=FMath::Max(JumpPeak,float(F->GetActorLocation().Z-Origin.Z));
    if(Stage==EStage::Zooming && Now>Started+.055f && FovAtMiddle==0)FovAtMiddle=Camera->FieldOfView;
    if(Now<Due)return;
    switch(Stage)
    {
    case EStage::Settle:
        StandingEye=Camera->GetComponentLocation().Z-F->GetActorLocation().Z+F->GetCapsuleComponent()->GetScaledCapsuleHalfHeight();
        Stage=EStage::BeginMove;break;
    case EStage::BeginMove:
        Origin=F->GetActorLocation();Key(PC,Cases[Index].Modifier,IE_Pressed);Key(PC,Cases[Index].Key,IE_Pressed);
        Due=Now+.48f;Stage=EStage::Moving;break;
    case EStage::Moving:
    {
        const auto& Case=Cases[Index];
        const FVector2D Delta=FVector2D(F->GetActorLocation()-Origin);
        const float Directed=FVector2D::DotProduct(Delta,Case.Direction);
        const float Speed=F->GetVelocity().Size2D();
        Check(Case.Label,Directed>65.f && FMath::Abs(Speed-Case.ExpectedSpeed)<60.f,Directed,Speed);
        if(Case.Modifier==EKeys::LeftControl)
        {
            const float Eye=Camera->GetComponentLocation().Z-F->GetActorLocation().Z+F->GetCapsuleComponent()->GetScaledCapsuleHalfHeight();
            Check(TEXT("crouched_eye_and_capsule"),F->bIsCrouched && StandingEye-Eye>30,StandingEye,Eye);
        }
        Key(PC,Case.Key,IE_Released);Key(PC,Case.Modifier,IE_Released);
        Due=Now+.36f;Stage=EStage::Braking;break;
    }
    case EStage::Braking:
        Check(TEXT("movement_released"),F->GetVelocity().Size2D()<2,F->GetVelocity().Size2D());
        ResetPose(PC,F);Due=Now+.24f;
        Stage=(++Index<UE_ARRAY_COUNT(Cases))?EStage::BeginMove:EStage::Jump;break;
    case EStage::Jump:
        Origin=F->GetActorLocation();JumpPeak=0;Key(PC,EKeys::SpaceBar,IE_Pressed);
        Due=Now+1.4f;Stage=EStage::Airborne;break;
    case EStage::Airborne:
        Key(PC,EKeys::SpaceBar,IE_Released);
        Check(TEXT("jump_lands"),JumpPeak>80 && F->GetCharacterMovement()->IsMovingOnGround(),JumpPeak);
        Stage=EStage::Look;break;
    case EStage::Look:
        PC->SetControlRotation(FRotator::ZeroRotator);
        Key(PC,EKeys::MouseX,IE_Axis,18.f);Key(PC,EKeys::MouseY,IE_Axis,6.f);
        Due=Now+.15f;Stage=EStage::Looking;break;
    case EStage::Looking:
    {
        const FRotator R=PC->GetControlRotation().GetNormalized();
        Check(TEXT("mouse_yaw_and_pitch"),FMath::Abs(R.Yaw)>.05f && FMath::Abs(R.Pitch)>.05f,R.Yaw,R.Pitch);
        Stage=EStage::ADS;break;
    }
    case EStage::ADS:
        FovAtStart=Camera->FieldOfView;FovAtMiddle=0;Started=Now;
        Key(PC,EKeys::RightMouseButton,IE_Pressed);Due=Now+.48f;Stage=EStage::Zooming;break;
    case EStage::Zooming:
        Check(TEXT("smooth_ads"),F->IsAiming() && FovAtStart>89 && FovAtMiddle<89 && FovAtMiddle>65 && FMath::Abs(Camera->FieldOfView-64)<.3,FovAtMiddle,Camera->FieldOfView);
        Key(PC,EKeys::RightMouseButton,IE_Released);Due=Now+.48f;Stage=EStage::Returning;break;
    case EStage::Returning:
        Check(TEXT("ads_release"),!F->IsAiming() && Camera->FieldOfView>89.7f,Camera->FieldOfView);
        Stage=EStage::Shot;break;
    case EStage::Shot:
        PC->SetControlRotation(FRotator(55,0,0));AmmoBefore=F->GetMagazineAmmo();
        Key(PC,EKeys::LeftMouseButton,IE_Pressed);Due=Now+.82f;Stage=EStage::Firing;break;
    case EStage::Firing:
    {
        AmmoAtRelease=F->GetMagazineAmmo();
        const float PitchDelta=PC->GetControlRotation().GetNormalized().Pitch-55;
        Check(TEXT("automatic_fire_interval"),AmmoBefore-AmmoAtRelease>=5 && AmmoBefore-AmmoAtRelease<=6,AmmoBefore-AmmoAtRelease);
        Check(TEXT("visible_controllable_recoil"),PitchDelta>.5 && PitchDelta<7,PitchDelta);
        Key(PC,EKeys::LeftMouseButton,IE_Released);Due=Now+.42f;Stage=EStage::Release;break;
    }
    case EStage::Release:
        Check(TEXT("trigger_release"),F->GetMagazineAmmo()==AmmoAtRelease,F->GetMagazineAmmo());
        Key(PC,EKeys::R,IE_Pressed);Key(PC,EKeys::R,IE_Released);Due=Now+.48f;Stage=EStage::Reload;break;
    case EStage::Reload:
        Check(TEXT("reload_in_progress"),F->IsReloading() && F->GetMagazineAmmo()==AmmoAtRelease,F->GetReloadAlpha());
        Key(PC,EKeys::LeftMouseButton,IE_Pressed);Key(PC,EKeys::LeftMouseButton,IE_Released);
        Due=Now+1.70f;Stage=EStage::Loading;break;
    case EStage::Loading:
        Check(TEXT("reload_transfers_exact_reserve"),!F->IsReloading() && F->GetMagazineAmmo()==30 && F->GetReserveAmmo()==120-(30-AmmoAtRelease),F->GetMagazineAmmo(),F->GetReserveAmmo());
        for(TActorIterator<ATempleFighter> It(World);It;++It)
            if(It->IsAlive() && F->GetTeam()!=It->GetTeam()){CoverTarget=*It;break;}
        if(!CoverTarget.IsValid())
        {
            Check(TEXT("cover_target_exists"),false);
            Stage=EStage::Done;
            break;
        }
        // Hold a real opposing Ranger on the far side of the existing Red Gate Screen.
        if(auto* Bot=Cast<AAIController>(CoverTarget->GetController())){Bot->StopMovement();Bot->SetActorTickEnabled(false);}
        CoverTarget->SetTriggerHeld(false);
        CoverTarget->TeleportTo(FVector(-7350,1260,710),FRotator(0,180,0));
        CoverTarget->GetCharacterMovement()->StopMovementImmediately();
        F->TeleportTo(FVector(-8030,1170,710),FRotator::ZeroRotator);
        F->GetCharacterMovement()->StopMovementImmediately();PC->SetControlRotation(FRotator::ZeroRotator);
        Due=Now+.32f;Stage=EStage::ApproachCover;break;
    case EStage::ApproachCover:
        Origin=F->GetActorLocation();Key(PC,EKeys::W,IE_Pressed);
        Due=Now+1.15f;Stage=EStage::AtCover;break;
    case EStage::AtCover:
    {
        Key(PC,EKeys::W,IE_Released);
        const FVector Eyes=F->GetPawnViewLocation(),Target=CoverTarget->GetActorLocation()+FVector(0,0,28);
        PC->SetControlRotation((Target-Eyes).Rotation());
        FHitResult Wall;
        const bool bBlocked=World->LineTraceSingleByChannel(Wall,Eyes,Target,ECC_Visibility,FCollisionQueryParams(SCENE_QUERY_STAT(CanopyCoverCheck),true,F));
        const float Distance=Wall.Distance;
        Check(TEXT("camera_stops_outside_solid_cover"),bBlocked && Wall.GetActor()!=CoverTarget.Get() && Distance>5.f && Distance<110.f,Distance,FVector::Dist2D(Origin,F->GetActorLocation()));
        if(!HandlingPictures.IsEmpty())FScreenshotRequest::RequestScreenshot(FPaths::Combine(HandlingPictures,TEXT("CloseCover.png")),true,false);
        CoverTargetHealth=CoverTarget->GetHealth();
        Key(PC,EKeys::LeftMouseButton,IE_Pressed);Due=Now+.32f;Stage=EStage::Impact;break;
    }
    case EStage::Impact:
        Key(PC,EKeys::LeftMouseButton,IE_Released);
        Check(TEXT("solid_cover_intercepts_automatic_fire"),CoverTarget.IsValid() && CoverTarget->GetHealth()==CoverTargetHealth && F->GetMagazineAmmo()<30,CoverTarget.IsValid()?CoverTarget->GetHealth():0,F->GetMagazineAmmo());
        Stage=EStage::Done;break;
    case EStage::Done:
        UE_LOG(LogTemp,Display,TEXT("TInput|result|%d"),Failures);
        FPlatformMisc::RequestExit(false);break;
    default:break;
    }
}
}
void StartTempleHandlingReview()
{
    FParse::Value(FCommandLine::Get(),TEXT("TempleHandlingImages="),TempleHandling::HandlingPictures);
    if(FParse::Param(FCommandLine::Get(),TEXT("TempleHandlingReview")))
        TempleHandling::Tick=FWorldDelegates::OnWorldPostActorTick.AddLambda([](UWorld* World,ELevelTick,float){TempleHandling::Frame(World);});
}
void StopTempleHandlingReview()
{
    if(TempleHandling::Tick.IsValid())FWorldDelegates::OnWorldPostActorTick.Remove(TempleHandling::Tick);
}
#endif
