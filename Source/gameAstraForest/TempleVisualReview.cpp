#if !UE_BUILD_SHIPPING
#include "TempleMatch.h"
#include "TempleFighter.h"
#include "Camera/PlayerCameraManager.h"
#include "UnrealClient.h"
#include "EngineUtils.h"
#include "Engine/World.h"
#include "HAL/FileManager.h"
#include "HAL/PlatformMisc.h"
#include "Misc/CommandLine.h"
#include "Misc/Paths.h"
#include "NavigationSystem.h"
#include "NavigationPath.h"
#include "ProfilingDebugging/CsvProfiler.h"

CSV_DEFINE_CATEGORY(TempleMatch,true);

namespace
{
FDelegateHandle VisualTick;
FString VisualDirectory;
TSet<FString> Recorded;
float ActiveAt=-1,FinishedAt=-1,LastPicture=-10,NextRouteAt=0;
TArray<FVector> Path;
int32 ReviewWaypointIndex=0, ReviewDestination=0, MeasureFrames=2100;
bool bReplayed=false, bMeasuring=false, bCaptureRequested=false, bCaptureStopped=false;

bool Photograph(UWorld* World,const TCHAR* Label)
{
    if(bMeasuring || Recorded.Contains(Label) || FScreenshotRequest::IsScreenshotRequested() || World->GetTimeSeconds()-LastPicture<.48f)return false;
    LastPicture=World->GetTimeSeconds();
    Recorded.Add(Label);
    FScreenshotRequest::RequestScreenshot(FPaths::Combine(VisualDirectory,FString(Label)+TEXT(".png")),true,false);
    return true;
}
void FollowCauseway(ATemplePlayerController* PC,ATempleFighter* Fighter,float Now)
{
    UWorld* World=PC->GetWorld();
    static const FVector Destinations[]={{-2850,1870,415},{1250,700,430},{3100,0,1200},{-1200,5300,500},{-6400,4000,500}};
    const FVector Here=Fighter->GetActorLocation();
    if(FVector::Dist2D(Here,Destinations[ReviewDestination])<190)
    {
        ReviewDestination=(ReviewDestination+1)%UE_ARRAY_COUNT(Destinations);
        Path.Reset();
    }
    if(Now>NextRouteAt && (ReviewWaypointIndex>=Path.Num() || FVector::Dist2D(Here,Path[ReviewWaypointIndex])>1800 || Fighter->GetVelocity().Size2D()<40))
    {
        UNavigationPath* Route=UNavigationSystemV1::FindPathToLocationSynchronously(World,Here,Destinations[ReviewDestination],Fighter);
        if(Route && Route->IsValid()){Path=Route->PathPoints;ReviewWaypointIndex=1;}
        NextRouteAt=Now+2;
    }
    while(ReviewWaypointIndex<Path.Num() && FVector::Dist2D(Fighter->GetActorLocation(),Path[ReviewWaypointIndex])<85)++ReviewWaypointIndex;
    if(ReviewWaypointIndex<Path.Num())
    {
        const FVector Heading=(Path[ReviewWaypointIndex]-Fighter->GetActorLocation()).GetSafeNormal2D();
        Fighter->AddMovementInput(Heading,1);
        PC->SetControlRotation(FMath::RInterpTo(PC->GetControlRotation(),Heading.Rotation(),World->GetDeltaSeconds(),5));
    }
}
void VisualFrame(UWorld* World)
{
    if(!World || !World->IsGameWorld() || World->GetNetMode()==NM_DedicatedServer || !World->GetMapName().Contains(TEXT("L_CanopyDeathmatch")))return;
    auto* State=World->GetGameState<ATempleGameState>();
    auto* PC=Cast<ATemplePlayerController>(World->GetFirstPlayerController());
    if(!State || !PC || !PC->IsLocalController())return;
    const float Now=World->GetTimeSeconds();
    auto* Fighter=Cast<ATempleFighter>(PC->GetPawn());
    if(bMeasuring && State->Phase==2 && Fighter)
    {
        if(ActiveAt<0)ActiveAt=Now;
        if(!bCaptureRequested && Now-ActiveAt>16)
        {
            bCaptureRequested=true;
            FCsvProfiler::Get()->BeginCapture(MeasureFrames,VisualDirectory,TEXT("FrameTimes.csv"));
        }
        CSV_CUSTOM_STAT(TempleMatch,Roster,State->PlayerArray.Num(),ECsvCustomStatOp::Set);
        CSV_CUSTOM_STAT(TempleMatch,Score,State->RedScore+State->BlueScore,ECsvCustomStatOp::Set);
        CSV_CUSTOM_STAT(TempleMatch,Alive,int32(Fighter->IsAlive()),ECsvCustomStatOp::Set);
        CSV_CUSTOM_STAT(TempleMatch,Speed,float(Fighter->GetVelocity().Size2D()/100.),ECsvCustomStatOp::Set);
    }
    if(bReplayed)
    {
        if(State->Phase==1)
        {
            if(Fighter && Fighter->GetTeam()!=1)
            {
                PC->JoinTeam(1);
                if(auto* NewFighter=Cast<ATempleFighter>(PC->GetPawn());NewFighter && NewFighter->GetTeam()==1 && PC->PlayerCameraManager)
                {
                    FMinimalViewInfo Eye;
                    NewFighter->CalcCamera(0.f,Eye);
                    UE_LOG(LogTemp,Display,TEXT("Canopy replay view: camera-to-new-eye %.3f cm, team %d"),
                           FVector::Distance(Eye.Location,PC->PlayerCameraManager->GetCameraLocation()),NewFighter->GetTeam());
                }
            }
            Photograph(World,TEXT("ReplayCountdown"));
        }
        if(State->Phase==2 && Fighter && Fighter->GetTeam()==1 && Fighter->IsFirstPersonViewSettled())
        {
            if(!Recorded.Contains(TEXT("BlueSpawn"))) Photograph(World,TEXT("BlueSpawn"));
            else if(!FScreenshotRequest::IsScreenshotRequested()) FPlatformMisc::RequestExit(false);
        }
        return;
    }
    if(State->Phase==1 && State->PhaseEndsAt-Now<1.9f)Photograph(World,TEXT("Countdown"));
    if(State->Phase==3)
    {
        if(bMeasuring && bCaptureRequested && !bCaptureStopped && FCsvProfiler::IsCapturing())
        {
            bCaptureStopped=true;
            FCsvProfiler::Get()->EndCapture();
        }
        if(FinishedAt<0)FinishedAt=Now;
        if(Now-FinishedAt>.6f)Photograph(World,TEXT("Result"));
        if(Now-FinishedAt>2.f && Recorded.Contains(TEXT("Result"))){PC->ReplayMatch();bReplayed=true;}
        return;
    }
    if(State->Phase!=2 || !Fighter)return;
    if(ActiveAt<0)ActiveAt=Now;
    const float T=Now-ActiveAt;
    if(!Fighter->IsAlive()){Photograph(World,TEXT("Respawn"));Path.Reset();return;}
    if(T>.7f)Photograph(World,TEXT("Spawn"));
    if(T>1.45f && T<2.f)Photograph(World,TEXT("Base"));
    if(T>2.f && T<3.5f)
    {
        PC->SetScoreboardVisible(true);
        if(T>2.3f)Photograph(World,TEXT("Scoreboard"));
        return;
    }
    PC->SetScoreboardVisible(false);
    if(T>4 && T<5.5f)
    {
        Fighter->SetAiming(true);
        if(T>4.6f)Photograph(World,TEXT("Aim"));
        return;
    }
    if(T>5.5f && T<6.15f){Fighter->SetTriggerHeld(true);if(T>5.73f)Photograph(World,TEXT("Firing"));return;}
    if(T>6.15f && T<7.8f)
    {
        Fighter->SetTriggerHeld(false);Fighter->SetAiming(false);Fighter->StartReload();
        if(T>6.6f && Fighter->IsReloading())Photograph(World,TEXT("Reload"));
        if(T>7.2f && Fighter->IsReloading())Photograph(World,TEXT("ReloadSeat"));
        return;
    }
    if(T<7.8f)return;
    FollowCauseway(PC,Fighter,Now);
    ATempleFighter* Opponent=nullptr;
    float Best=4800;
    for(TActorIterator<ATempleFighter> It(World);It;++It)
    {
        if(!It->IsAlive() || It->GetTeam()==Fighter->GetTeam())continue;
        const float D=FVector::Dist2D(It->GetActorLocation(),Fighter->GetActorLocation());
        if(D<Best && PC->LineOfSightTo(*It)){Opponent=*It;Best=D;}
    }
    if(Opponent)
    {
        PC->SetControlRotation((Opponent->GetActorLocation()+FVector(0,0,28)-Fighter->GetPawnViewLocation()).Rotation());
        Fighter->SetTriggerHeld(true);
        if(T>10 && Fighter->GetMagazineAmmo()<Fighter->GetMagazineCapacity()) Photograph(World,TEXT("Encounter"));
        if(T>35 && Fighter->GetMagazineAmmo()<Fighter->GetMagazineCapacity()) Photograph(World,TEXT("Midmatch"));
    }
    else Fighter->SetTriggerHeld(false);
    if(!State->Feed.IsEmpty() && T>8)Photograph(World,TEXT("Feed"));
    if(Fighter->GetHealth()<Fighter->GetMaxHealth())Photograph(World,TEXT("Damage"));
    if(T>20 && FVector::Dist2D(Fighter->GetActorLocation(),FVector(-2850,1870,415))<700)Photograph(World,TEXT("Causeway"));
}
}
void StartTempleVisualReview()
{
    if(!FParse::Value(FCommandLine::Get(),TEXT("TempleVisualReview="),VisualDirectory))return;
    bMeasuring=FParse::Param(FCommandLine::Get(),TEXT("TempleMeasure"));
    FParse::Value(FCommandLine::Get(),TEXT("TempleMeasureFrames="),MeasureFrames);
    MeasureFrames=FMath::Clamp(MeasureFrames,600,40000);
    VisualDirectory=FPaths::ConvertRelativePathToFull(VisualDirectory);
    IFileManager::Get().MakeDirectory(*VisualDirectory,true);
    VisualTick=FWorldDelegates::OnWorldPostActorTick.AddLambda([](UWorld* World,ELevelTick,float){VisualFrame(World);});
}
void StopTempleVisualReview(){if(VisualTick.IsValid())FWorldDelegates::OnWorldPostActorTick.Remove(VisualTick);}
#endif
