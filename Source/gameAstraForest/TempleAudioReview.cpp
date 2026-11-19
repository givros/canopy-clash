#if !UE_BUILD_SHIPPING
#include "TempleFighter.h"
#include "TempleBotController.h"
#include "TempleMatch.h"
#include "AudioMixerBlueprintLibrary.h"
#include "Components/CapsuleComponent.h"
#include "EngineUtils.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "LandscapeHeightfieldCollisionComponent.h"
#include "Misc/CommandLine.h"

namespace TempleAudioReview
{
const TCHAR* Names[] = {TEXT("Idle"),TEXT("ForestWalk"),TEXT("StoneWalk"),TEXT("Crouch"),TEXT("OtherLeft"),
    TEXT("OtherRight"),TEXT("Report"),TEXT("Reload"),TEXT("Confirm"),TEXT("Contact"),TEXT("Stopped")};
const FVector Bridge(-3640,1767,0);
const FVector Along = FVector(700,101,0).GetSafeNormal();
FDelegateHandle Hook;
FString Output;
int32 Stage = INDEX_NONE;
float Started = 0, LastReport = -1000;
bool bRecording = false, bTriggered = false;
TWeakObjectPtr<ATempleFighter> AudioPartnerFighter;
FVector Forest;

bool Ground(UWorld* World, FVector XY, FHitResult& Hit)
{
    FCollisionQueryParams Query(SCENE_QUERY_STAT(TempleAudioFloor),false);
    for (TActorIterator<ATempleFighter> It(World); It; ++It) Query.AddIgnoredActor(*It);
    return World->LineTraceSingleByChannel(Hit,FVector(XY.X,XY.Y,1030),FVector(XY.X,XY.Y,100),ECC_Visibility,Query);
}

bool ForestLane(UWorld* World)
{
    for (int32 Y = 750; Y <= 2700; Y += 160)
    for (int32 X = -7900; X <= -5400; X += 150)
    {
        bool bWalkable = true;
        for (int32 Sample = 0; Sample <= 7; ++Sample)
        {
            FHitResult Hit;
            if (!Ground(World,FVector(X+120*Sample,Y,0),Hit) || Hit.ImpactNormal.Z < .85f ||
                !Hit.GetComponent()->IsA<ULandscapeHeightfieldCollisionComponent>())
            { bWalkable=false; break; }
        }
        if (bWalkable) { Forest=FVector(X,Y,0); return true; }
    }
    return false;
}

void Seat(ATempleFighter* F, FVector Where, float Yaw)
{
    FHitResult Hit;
    if (!Ground(F->GetWorld(),Where,Hit)) return;
    const FRotator Facing(0,Yaw,0);
    F->GetCharacterMovement()->StopMovementImmediately();
    F->TeleportTo(Hit.ImpactPoint+FVector(0,0,F->GetCapsuleComponent()->GetScaledCapsuleHalfHeight()+3),Facing);
    F->GetController()->SetControlRotation(Facing);
}

void Review(UWorld* W, ELevelTick, float)
{
    if (!W || !W->IsGameWorld() || W->GetNetMode()!=NM_Standalone || !W->GetMapName().Contains(TEXT("L_CanopyDeathmatch"))) return;
    auto* PC = W->GetFirstPlayerController();
    auto* F = PC ? Cast<ATempleFighter>(PC->GetPawn()) : nullptr;
    auto* Match = W->GetGameState<ATempleGameState>();
    if (!F || !Match || Match->Phase!=2) return;
    const float Now=W->GetTimeSeconds();
    if (Stage == INDEX_NONE)
    {
        for (TActorIterator<ATempleFighter> It(W); It; ++It)
        {
            auto* Bot = Cast<ATempleBotController>(It->GetController());
            if (!Bot) continue;
            Bot->StopMovement();
            Bot->SetActorTickEnabled(false);
            It->SetTriggerHeld(false);
            AudioPartnerFighter=*It;
        }
        if (!AudioPartnerFighter.IsValid() || !ForestLane(W)) return;
        Stage=0; Started=Now;
        Seat(F,Bridge,0); Seat(AudioPartnerFighter.Get(),Bridge+Along*750,180);
    }
    if (Stage >= UE_ARRAY_COUNT(Names))
    {
        if (Now-Started>1.5f) FPlatformMisc::RequestExit(false);
        return;
    }
    const float T=Now-Started;
    auto* Bot=AudioPartnerFighter.Get();
    if (!Bot) return;
    if (!bRecording && T>=.35f)
    {
        UAudioMixerBlueprintLibrary::StartRecordingOutput(W,3.f);
        bRecording=true;
        UE_LOG(LogTemp,Display,TEXT("TempleMix begin %s t=%.3f"),Names[Stage],Now);
    }
    if (T>=.72f && !bTriggered)
    {
        bTriggered=true;
        if (Stage==6 || Stage==9)
        {
            FVector Eye; FRotator Look; F->GetActorEyesViewPoint(Eye,Look);
            PC->SetControlRotation(Stage==6 ? FRotator(65,0,0) : (Bot->GetActorLocation()-Eye).Rotation());
            F->SetAiming(true);
            F->SetTriggerHeld(true); F->SetTriggerHeld(false);
            LastReport=F->GetLocalHitTime();
            UE_LOG(LogTemp,Display,TEXT("TempleMix action %s ammo=%d health=%.1f hit=%.3f world=%.3f"),
                Names[Stage],F->GetMagazineAmmo(),Bot->GetHealth(),LastReport,Now);
        }
        if (Stage==7) F->StartReload();
        if (Stage==8) F->ClientConfirmHit(false);
    }
    if (T>=.65f && T<=2.35f)
    {
        const FVector Dir=Stage==1?FVector::ForwardVector:Along;
        if (Stage>=1 && Stage<=3) F->AddMovementInput(Dir,1,true);
        if (Stage==4 || Stage==5) Bot->AddMovementInput(T<1.5f ? Dir : -Dir,1,true);
    }
    if (T<3.f) return;
    UAudioMixerBlueprintLibrary::StopRecordingOutputToAnyPath(W,EAudioRecordingExportType::WavFile,Names[Stage],Output);
    UE_LOG(LogTemp,Display,TEXT("TempleMix end %s t=%.3f ammo=%d otherHealth=%.1f"),Names[Stage],Now,F->GetMagazineAmmo(),Bot->GetHealth());
    ++Stage; Started=Now; bRecording=false; bTriggered=false;
    if (Stage==1) Seat(F,Forest,0);
    if (Stage==2 || Stage==3 || Stage==6 || Stage==9)
    {
        F->UnCrouch(); Seat(F,Bridge,0); Seat(Bot,Bridge+Along*735,180);
        if (Stage==3) F->Crouch();
    }
    if (Stage==4 || Stage==5)
    {
        F->UnCrouch(); Seat(F,Bridge,Stage==4?98.f:-82.f); Seat(Bot,Bridge+Along*270,8);
    }
}
}

void StartTempleAudioReview()
{
    if (!FParse::Param(FCommandLine::Get(),TEXT("TempleAudioReview")) ||
        !FParse::Value(FCommandLine::Get(),TEXT("TempleAudioOut="),TempleAudioReview::Output)) return;
    TempleAudioReview::Hook=FWorldDelegates::OnWorldPostActorTick.AddStatic(TempleAudioReview::Review);
}
void StopTempleAudioReview()
{
    if (TempleAudioReview::Hook.IsValid()) FWorldDelegates::OnWorldPostActorTick.Remove(TempleAudioReview::Hook);
}
#endif
