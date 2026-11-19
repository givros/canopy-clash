#if !UE_BUILD_SHIPPING
#include "TempleBotController.h"
#include "TempleFighter.h"
#include "TempleMatch.h"
#include "AudioMixerBlueprintLibrary.h"
#include "AudioDevice.h"
#include "Camera/CameraComponent.h"
#include "Components/CapsuleComponent.h"
#include "Components/PointLightComponent.h"
#include "Engine/GameViewportClient.h"
#include "EngineUtils.h"
#include "GameFramework/InputDeviceLibrary.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/PlayerState.h"
#include "InputKeyEventArgs.h"
#include "Misc/CommandLine.h"

namespace TempleLatencyTest
{
FDelegateHandle Hook;
FString Directory,Role;
int32 Stage=0;
double Epoch=0,Start=0;
bool bRecording=false,bCountdownSent=false;
float LastFX=-1000,LastFOV=90.f;
int32 PreviousAmmo=-1;
bool PreviousReload=false;
TWeakObjectPtr<ATempleFighter> CurrentPawn;

void Event(const TCHAR* Label,UWorld* W,ATempleFighter* F)
{
    auto* PS=F->GetPlayerState<APlayerState>();
    const auto* Camera=F->FindComponentByClass<UCameraComponent>();
    const auto* Flash=F->FindComponentByClass<UPointLightComponent>();
    UE_LOG(LogTemp,Display,TEXT("TempleLatency %s clock=%.6f world=%.4f frame=%llu phase=%d ammo=%d reserve=%d reload=%d hit=%.4f fx=%.4f fov=%.3f light=%d ping=%.1f"),
        Label,FPlatformTime::Seconds(),W->GetTimeSeconds(),GFrameCounter,Stage,F->GetMagazineAmmo(),F->GetReserveAmmo(),F->IsReloading(),
        F->GetLocalHitTime(),F->GetLocalShotTime(),Camera?Camera->FieldOfView:0.f,Flash&&Flash->IsVisible(),PS?PS->GetPingInMilliseconds():-1.f);
}
void Key(ATemplePlayerController* PC,FKey K,bool Down)
{
    if(auto* Viewport=PC->GetWorld()->GetGameViewport())
    {
        const auto Device=UInputDeviceLibrary::GetPrimaryInputDeviceForUser(PC->GetPlatformUserId());
        Viewport->InputKey(FInputKeyEventArgs::CreateSimulated(K,Down?IE_Pressed:IE_Released,Down?1.f:0.f,-1,Device,false,Viewport->Viewport));
    }
}
void SeatForContact(ATempleFighter* F,float X,float Y,float Yaw)
{
    FHitResult Hit;
    FCollisionQueryParams Query(SCENE_QUERY_STAT(TempleLatencyContact),true,F);
    if(!F->GetWorld()->LineTraceSingleByChannel(Hit,FVector(X,Y,850),FVector(X,Y,-110),ECC_Visibility,Query))return;
    F->GetCharacterMovement()->StopMovementImmediately();
    F->TeleportTo(Hit.ImpactPoint+FVector(0,0,F->GetCapsuleComponent()->GetScaledCapsuleHalfHeight()+2),FRotator(0,Yaw,0));
    F->GetController()->SetControlRotation(FRotator(0,Yaw,0));
}
void Review(UWorld* W,ELevelTick,float)
{
    if(!W||!W->IsGameWorld()||!W->GetMapName().Contains(TEXT("L_CanopyDeathmatch")))return;
    if(!Epoch)Epoch=FPlatformTime::Seconds();
    const double Now=FPlatformTime::Seconds();
    if(Now-Epoch>65.){FPlatformMisc::RequestExit(false);return;}
    auto* G=W->GetGameState<ATempleGameState>();
    if(!G)return;
    if(Role==TEXT("Host"))
    {
        for(FConstPlayerControllerIterator It=W->GetPlayerControllerIterator();It;++It)
        {
            auto* PC=It->Get();
            auto* F=PC&&!PC->IsLocalController()?Cast<ATempleFighter>(PC->GetPawn()):nullptr;
            if(!F)continue;
            static bool bSeated=false;
            if(!bSeated && FPaths::FileExists(Directory/TEXT("test_contact")))
            {
                if(auto* Target=Cast<ATempleFighter>(W->GetFirstPlayerController()->GetPawn()))
                {
                    SeatForContact(F,-3640,1767,8);SeatForContact(Target,-2940,1868,188);
                    bSeated=true;
                }
            }
            static bool bEliminatedForReview=false;
            if (!bEliminatedForReview && FPaths::FileExists(Directory/TEXT("test_death")))
            {F->Eliminate(nullptr);bEliminatedForReview=true;}
            if (G->Phase==3 && FPaths::FileExists(Directory/TEXT("test_countdown")))
                if (auto* Mode=W->GetAuthGameMode<ATempleMatchMode>()) Mode->Replay();
            if(F->GetMagazineAmmo()!=PreviousAmmo || F->IsReloading()!=PreviousReload)
            {Event(TEXT("authority"),W,F);PreviousAmmo=F->GetMagazineAmmo();PreviousReload=F->IsReloading();}
        }
        if(FPaths::FileExists(Directory/TEXT("done")))FPlatformMisc::RequestExit(false);
        return;
    }
    auto* PC=Cast<ATemplePlayerController>(W->GetFirstPlayerController());
    auto* F=PC?Cast<ATempleFighter>(PC->GetPawn()):nullptr;
    if(!F)return;
    if(CurrentPawn!=F){CurrentPawn=F; LastFX=F->GetLocalShotTime();}
    if(F->GetLocalShotTime()!=LastFX){LastFX=F->GetLocalShotTime();Event(TEXT("cosmetic"),W,F);}
    if(F->GetMagazineAmmo()!=PreviousAmmo||F->IsReloading()!=PreviousReload)
    {Event(TEXT("replicated"),W,F);PreviousAmmo=F->GetMagazineAmmo();PreviousReload=F->IsReloading();}
    auto* Camera=F->FindComponentByClass<UCameraComponent>();
    // NullRHI omits the viewport draw that normally submits the local player's listener transform.
    if (Camera && FParse::Param(FCommandLine::Get(),TEXT("NullRHI")))
        if (FAudioDeviceHandle Device=W->GetAudioDevice())
            Device->SetListener(W,0,Camera->GetComponentTransform(),W->GetDeltaSeconds());
    if(Camera&&FMath::Abs(Camera->FieldOfView-LastFOV)>.3f){LastFOV=Camera->FieldOfView;Event(TEXT("lens"),W,F);}
    static float CountdownCheckAt=0;
    if(G->Phase==1 && !bCountdownSent)
    {
        Event(TEXT("countdown_attempt"),W,F);F->SetTriggerHeld(true);bCountdownSent=true;
        CountdownCheckAt=W->GetTimeSeconds()+.35f;
    }
    if (CountdownCheckAt>0 && W->GetTimeSeconds()>=CountdownCheckAt)
    {F->SetTriggerHeld(false);Event(TEXT("countdown_checked"),W,F);CountdownCheckAt=0;}
    static bool bDeathGuardChecked=false;
    if (Start && Now-Start>15.0 && !F->IsAlive() && !bDeathGuardChecked)
    {
        Event(TEXT("dead_attempt"),W,F);F->SetTriggerHeld(true);F->SetTriggerHeld(false);
        Event(TEXT("dead_checked"),W,F);bDeathGuardChecked=true;
        FFileHelper::SaveStringToFile(TEXT("ready"),*(Directory/TEXT("test_countdown")));
        bCountdownSent=false;
    }
    if (Start && Now-Start>15.5 && bDeathGuardChecked && bCountdownSent && CountdownCheckAt==0)
    {
        FFileHelper::SaveStringToFile(TEXT("complete"),*(Directory/TEXT("done")));
        FPlatformMisc::RequestExit(false);return;
    }
    if(Role==TEXT("Local") && bDeathGuardChecked && G->Phase==3)
        if(auto* Mode=W->GetAuthGameMode<ATempleMatchMode>())Mode->Replay();
    if(G->Phase!=2)return;
    if(!Start)
    {
        if(Now-Epoch<7.)return;
        PC->SetControlRotation(FRotator(70,0,0));
        if(W->GetNetMode()==NM_Standalone)
            for(TActorIterator<ATempleBotController> It(W);It;++It){It->StopMovement();It->SetActorTickEnabled(false);}
        UAudioMixerBlueprintLibrary::StartRecordingOutput(W,18);
        bRecording=true; Start=Now;Event(TEXT("record_start"),W,F);
    }
    const double T=Now-Start;
    struct FAction{double Time;FKey Button;bool Down;const TCHAR* Name;};
    const FAction Actions[]={
        {.55,EKeys::RightMouseButton,true,TEXT("ads_down")},{1.1,EKeys::RightMouseButton,false,TEXT("ads_up")},
        {1.75,EKeys::LeftMouseButton,true,TEXT("tap_down")},{1.81,EKeys::LeftMouseButton,false,TEXT("tap_up")},
        {2.7,EKeys::LeftMouseButton,true,TEXT("burst_down")},{3.33,EKeys::LeftMouseButton,false,TEXT("burst_up")},
        {3.9,EKeys::R,true,TEXT("reload_down")},{3.96,EKeys::R,false,TEXT("reload_up")},
        {4.23,EKeys::LeftMouseButton,true,TEXT("blocked_reload_down")},{4.29,EKeys::LeftMouseButton,false,TEXT("blocked_reload_up")},
        {6.65,EKeys::LeftMouseButton,true,TEXT("drain_down")},{11.24,EKeys::LeftMouseButton,false,TEXT("drain_up")},
        {11.45,EKeys::LeftMouseButton,true,TEXT("empty_down")},{11.51,EKeys::LeftMouseButton,false,TEXT("empty_up")}};
    if(Stage<UE_ARRAY_COUNT(Actions) && T>=Actions[Stage].Time)
    {const FAction& A=Actions[Stage];Event(A.Name,W,F);Key(PC,A.Button,A.Down);++Stage;}
    static bool bEarly=false,bEmpty=false;
    if(T>=3.95 && !bEarly)
    {
        Event(TEXT("pre_ack_reload_attempt"),W,F);F->SetTriggerHeld(true);F->SetTriggerHeld(false);bEarly=true;
    }
    if(T>7 && T<11.5 && F->GetMagazineAmmo()==0 && !F->IsReloading() && !bEmpty)
    {
        F->SetTriggerHeld(false);Event(TEXT("empty_before_reload_attempt"),W,F);
        F->SetTriggerHeld(true);F->SetTriggerHeld(false);bEmpty=true;
    }
    if(T>14.2 && bRecording)
    {
        UAudioMixerBlueprintLibrary::StopRecordingOutputToAnyPath(W,EAudioRecordingExportType::WavFile,TEXT("Output"),Directory);
        Event(TEXT("record_end"),W,F);bRecording=false;
    }
    static bool bGuardRequested=false;
    static bool bContactRequested=false,bContactSent=false;
    if(T>14.3 && Role!=TEXT("Local") && !bContactRequested)
    {FFileHelper::SaveStringToFile(TEXT("ready"),*(Directory/TEXT("test_contact")));bContactRequested=true;}
    if(bContactRequested && !bContactSent && T>15.0 && FMath::Abs(F->GetActorLocation().X+3640)<65)
    {
        for(TActorIterator<ATempleFighter> It(W);It;++It)
        {
            if(*It==F || It->GetTeam()==F->GetTeam() || !It->IsAlive() || FMath::Abs(It->GetActorLocation().X+2940)>100) continue;
            PC->SetControlRotation((It->GetActorLocation()-F->GetPawnViewLocation()).Rotation());
            if(T>15.45)
            {
                Event(TEXT("contact_input"),W,F);F->SetTriggerHeld(true);F->SetTriggerHeld(false);
                Event(TEXT("contact_immediate"),W,F);bContactSent=true;
            }
            break;
        }
    }
    if(T>16.2 && !bGuardRequested)
    {
        bGuardRequested=true;
        Event(TEXT("contact_received"),W,F);
        if(Role==TEXT("Local"))
        {
            F->Eliminate(nullptr);
        }
        else FFileHelper::SaveStringToFile(TEXT("ready"),*(Directory/TEXT("test_death")));
    }
}
}
void StartTempleLatencyReview()
{
    using namespace TempleLatencyTest;
    if(!FParse::Value(FCommandLine::Get(),TEXT("TempleLatency="),Role)||!FParse::Value(FCommandLine::Get(),TEXT("TempleLatencyOut="),Directory))return;
    Hook=FWorldDelegates::OnWorldPostActorTick.AddStatic(Review);
}
void StopTempleLatencyReview()
{
    if(TempleLatencyTest::Hook.IsValid())FWorldDelegates::OnWorldPostActorTick.Remove(TempleLatencyTest::Hook);
}
#endif
