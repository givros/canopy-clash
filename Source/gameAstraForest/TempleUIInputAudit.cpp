#if !UE_BUILD_SHIPPING
#include "TempleHUD.h"
#include "TempleMatch.h"
#include "Camera/PlayerCameraManager.h"
#include "Blueprint/WidgetBlueprintLibrary.h"
#include "Components/Button.h"
#include "Components/EditableTextBox.h"
#include "Components/TextBlock.h"
#include "Containers/Ticker.h"
#include "Engine/Engine.h"
#include "Engine/GameViewportClient.h"
#include "Engine/World.h"
#include "Framework/Application/SlateApplication.h"
#include "GameFramework/InputDeviceLibrary.h"
#include "GameFramework/Pawn.h"
#include "HAL/FileManager.h"
#include "HAL/PlatformMisc.h"
#include "Input/HittestGrid.h"
#include "InputKeyEventArgs.h"
#include "Layout/WidgetPath.h"
#include "Misc/CommandLine.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "UnrealClient.h"
#include "Widgets/SWindow.h"

namespace TempleUIAudit
{
FTSTicker::FDelegateHandle Tick;
FString File;
TArray<FString> Results;
TWeakObjectPtr<UTempleCombatHUD> CachedHUD;
enum class EStep
{
    Start, OpenRoster, TabOpened, ChooseTeam, TeamClicked, TabReleased, ReopenRoster, TabReopened, EscapeClosed,
    MenuOpened, OpenControls, ControlsOpened, LeaveControls, OpenPrivate, TryAddress, BadAddress, OpenTeams, TeamsOpened, ResumeMenu,
    Resumed, End, ClickReplay, ReplayClicked, QuitMenu, Done
};
EStep Step = EStep::Start;
double NextCheck = 0;
double StartedAt = 0;
uint8 TargetTeam = 255;
bool bAwaitingTeamSpawn = false;

void Record(const FString& Name, bool Passed, const FString& Details=FString())
{
    const FString Escaped=Details.ReplaceCharWithEscapedChar();
    Results.Add(FString::Printf(TEXT("{\"name\":\"%s\",\"passed\":%s,\"detail\":\"%s\"}"),
        *Name, Passed ? TEXT("true") : TEXT("false"), *Escaped));
    UE_LOG(LogTemp,Display,TEXT("TempleUIAudit %s %s %s"),Passed?TEXT("PASS"):TEXT("FAIL"),*Name,*Details);
}

void Finish(bool Passed)
{
    Step=EStep::Done;
    IFileManager::Get().MakeDirectory(*FPaths::GetPath(File),true);
    const FString Body=FString::Printf(TEXT("{\"passed\":%s,\"checks\":[%s]}"),Passed?TEXT("true"):TEXT("false"),*FString::Join(Results,TEXT(",\n")));
    FFileHelper::SaveStringToFile(Body,*File,FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
    FPlatformMisc::RequestExit(false);
}

bool Require(const FString& Name, bool Passed, const FString& Details=FString())
{
    Record(Name,Passed,Details);
    if(!Passed) Finish(false);
    return Passed;
}

void Next(EStep Stage, UWorld* World, double Delay=.38)
{
    Step=Stage;
    NextCheck=FPlatformTime::Seconds()+Delay;
}

bool SlateKey(FKey Key, bool Down)
{
    const FKeyEvent Input(Key,FModifierKeysState(),0,false,0,0);
    auto& App=FSlateApplication::Get();
    return Down?App.ProcessKeyDownEvent(Input):App.ProcessKeyUpEvent(Input);
}

FWidgetPath HitAt(SWindow& Window, const FVector2D& Location)
{
    TArray<FWidgetAndPointer> Hits=Window.GetHittestGrid().GetBubblePath(Location,0.f,false,0);
    return Hits.IsEmpty() ? FWidgetPath() : FWidgetPath(MakeArrayView(Hits));
}

bool Click(UTempleCombatHUD& HUD, SWindow& Window, FName Name, FString ExpectedCaption)
{
    auto* Button=Cast<UButton>(HUD.GetWidgetFromName(Name));
    if(!Require(Name.ToString()+TEXT("_enabled"),Button && Button->GetIsEnabled() && Button->IsVisible())) return false;
    const auto* Caption=Cast<UTextBlock>(Button->GetContent());
    if(!Require(Name.ToString()+TEXT("_caption"),Caption && Caption->GetText().ToString()==ExpectedCaption,
                Caption?Caption->GetText().ToString():TEXT("missing"))) return false;

    TSharedPtr<SWidget> ButtonSlate=Button->GetCachedWidget();
    const FGeometry& G=Button->GetCachedGeometry();
    const FVector2D Size=G.GetLocalSize();
    const FVector2D Center=G.LocalToAbsolute(Size*.5);
    const FWidgetPath AtCenter=HitAt(Window,Center);
    const FWidgetPath NearEdge=HitAt(Window,G.LocalToAbsolute(FVector2D(3,3)));
    const FWidgetPath Outside=HitAt(Window,G.LocalToAbsolute(FVector2D(-5,Size.Y*.5)));
    const FString Bounds=FString::Printf(TEXT("origin=(%.1f,%.1f), logical=%.1fx%.1f, center=(%.1f,%.1f), leaf=%s"),
        G.GetAbsolutePosition().X,G.GetAbsolutePosition().Y,Size.X,Size.Y,Center.X,Center.Y,
        AtCenter.IsValid()?*AtCenter.GetLastWidget()->GetTypeAsString():TEXT("none"));
    if(!Require(Name.ToString()+TEXT("_native_hit_box"),ButtonSlate && AtCenter.ContainsWidget(ButtonSlate.Get())
           && NearEdge.ContainsWidget(ButtonSlate.Get()) && !Outside.ContainsWidget(ButtonSlate.Get()),Bounds))return false;

    const TSet<FKey> Empty;
    TSet<FKey> Pressed;Pressed.Add(EKeys::LeftMouseButton);
    const int32 Pointer=FSlateApplication::CursorPointerIndex;
    const FPointerEvent Move(0,Pointer,Center,Center,Empty,FKey(),0,FModifierKeysState());
    const FPointerEvent Down(0,Pointer,Center,Center,Pressed,EKeys::LeftMouseButton,0,FModifierKeysState());
    const FPointerEvent Up(0,Pointer,Center,Center,Empty,EKeys::LeftMouseButton,0,FModifierKeysState());
    auto& App=FSlateApplication::Get();
    App.RoutePointerMoveEvent(AtCenter,Move,false);
    const bool DownHandled=App.RoutePointerDownEvent(AtCenter,Down).IsEventHandled();
    const bool WasPressed=Button->IsPressed();
    const bool UpHandled=App.RoutePointerUpEvent(AtCenter,Up).IsEventHandled();
    return Require(Name.ToString()+TEXT("_pointer_down_and_up"),DownHandled && WasPressed && UpHandled,
                   FString::Printf(TEXT("down=%d pressed=%d up=%d"),DownHandled,WasPressed,UpHandled));
}

void Shot(const TCHAR* Name)
{
    FScreenshotRequest::RequestScreenshot(FPaths::Combine(FPaths::GetPath(File),FString(Name)+TEXT(".png")),true,false);
}

bool CameraAtSpawn(ATemplePlayerController& Player,const TCHAR* Name)
{
    APawn* Pawn=Player.GetPawn();
    if(!Pawn || !Player.PlayerCameraManager) return Require(Name,false);
    FMinimalViewInfo Expected;
    Pawn->CalcCamera(0.f,Expected);
    const double Error=FVector::Distance(Expected.Location,Player.PlayerCameraManager->GetCameraLocation());
    return Require(Name,Player.GetViewTarget()==Pawn && Error<1.0,FString::Printf(TEXT("eye error %.3f cm"),Error));
}

void Frame(UWorld* World)
{
    if(Step==EStep::Done || !World || !World->IsGameWorld() || World->GetNetMode()!=NM_Standalone
       || !World->GetMapName().Contains(TEXT("L_CanopyDeathmatch")) || !FSlateApplication::IsInitialized()) return;
    auto* PC=Cast<ATemplePlayerController>(World->GetFirstPlayerController());
    auto* Match=World->GetGameState<ATempleGameState>();
    auto* PS=PC?PC->GetPlayerState<ATemplePlayerState>():nullptr;
    UGameViewportClient* Viewport=World->GetGameViewport();
    if(!PC || !PC->IsLocalController() || !PS || !Match || !Viewport || !Viewport->GetWindow().IsValid()) return;
    if(bAwaitingTeamSpawn && PS->Team==TargetTeam && PC->GetPawn())
    {
        if(!CameraAtSpawn(*PC,TEXT("team_respawn_camera"))) return;
        bAwaitingTeamSpawn=false;
    }
    const double Now=FPlatformTime::Seconds();
    if(StartedAt==0) StartedAt=Now;
    if(Now<NextCheck) return;
    if (Now-StartedAt>115) { Require(TEXT("completed_in_time"),false,FString::FromInt(static_cast<int32>(Step))); return; }
    if(!CachedHUD.IsValid())
    {
        TArray<UUserWidget*> Widgets;
        UWidgetBlueprintLibrary::GetAllWidgetsOfClass(World,Widgets,UTempleCombatHUD::StaticClass(),true);
        for(UUserWidget* Widget:Widgets) if(Widget->GetOwningPlayer()==PC) CachedHUD=Cast<UTempleCombatHUD>(Widget);
    }
    UTempleCombatHUD* HUD=CachedHUD.Get();
    if(!HUD || !HUD->GetCachedWidget().IsValid()) return;
    auto& App=FSlateApplication::Get();
    auto& Window=*Viewport->GetWindow();
    const auto SendGameKey=[&](FKey Key,EInputEvent Edge=IE_Pressed){
        // Inject at the game viewport with the local player's mapped keyboard device.
        const FInputDeviceId Device=UInputDeviceLibrary::GetPrimaryInputDeviceForUser(PC->GetPlatformUserId());
        return Viewport->InputKey(FInputKeyEventArgs::CreateSimulated(Key,Edge,Edge==IE_Pressed?1.f:0.f,-1,Device,false,Viewport->Viewport));
    };
    const auto IsHudFocus=[&](){
        auto Widget=HUD->GetCachedWidget();
        return Widget->HasUserFocus(0).IsSet() || Widget->HasUserFocusedDescendants(0);
    };
    switch(Step)
    {
    case EStep::Start:
        if(Match->Phase!=2 || PS->Team>1) return;
        {
            const double Start=Match->PhaseEndsAt-Match->PhaseDuration;
            const int32 DurationSeconds=FMath::CeilToInt32(Match->PhaseDuration);
            if(!Require(TEXT("match_clock_respects_start_and_expiry"),
                Match->RemainingPhaseSeconds(Start-.2)==DurationSeconds &&
                Match->RemainingPhaseSeconds(Start)==DurationSeconds &&
                Match->RemainingPhaseSeconds(Match->PhaseEndsAt-.2)==1 &&
                Match->RemainingPhaseSeconds(Match->PhaseEndsAt+.2)==0,
                FString::Printf(TEXT("configured=%d"),DurationSeconds))) return;
        }
        if(!Require(TEXT("gameplay_cursor_hidden"),!PC->bShowMouseCursor && !PC->bScoreboardVisible)) return;
        TargetTeam=1-PS->Team;
        Shot(TEXT("ActiveHUD"));
        Next(EStep::OpenRoster,World);
        break;
    case EStep::OpenRoster:
        SendGameKey(EKeys::Tab);
        Next(EStep::TabOpened,World);
        break;
    case EStep::TabOpened:
        if(!Require(TEXT("tab_press_opens_focus_and_cursor"),PC->bScoreboardVisible && PC->bShowMouseCursor && IsHudFocus(),
                    FString::Printf(TEXT("open=%d cursor=%d focus=%d"),PC->bScoreboardVisible,PC->bShowMouseCursor,IsHudFocus())))return;
        if(HUD->GetRosterPageCountForAudit()>1)
        {
            SlateKey(EKeys::PageDown,true);SlateKey(EKeys::PageDown,false);
            if(!Require(TEXT("page_down"),HUD->GetRosterPageForAudit()==1))return;
            SlateKey(EKeys::PageUp,true);SlateKey(EKeys::PageUp,false);
            if(!Require(TEXT("page_up"),HUD->GetRosterPageForAudit()==0))return;
        }
        Shot(TEXT("Roster"));
        Next(EStep::ChooseTeam,World);
        break;
    case EStep::ChooseTeam:
        if(!Click(*HUD,Window,TargetTeam==0?TEXT("JoinRed"):TEXT("JoinBlue"),
                  TargetTeam==0?TEXT("1   Join Red"):TEXT("2   Join Blue"))) return;
        if(!Require(TEXT("team_change_starts_respawn"),!PC->GetPawn() && PS->RespawnAt>Match->GetServerWorldTimeSeconds()))return;
        bAwaitingTeamSpawn=true;
        Next(EStep::TeamClicked,World);
        break;
    case EStep::TeamClicked:
        if(!Require(TEXT("pointer_changes_authoritative_team"),PS->Team==TargetTeam,FString::FromInt(PS->Team))) return;
        SlateKey(EKeys::Tab,false);
        Next(EStep::TabReleased,World);
        break;
    case EStep::TabReleased:
        if(!Require(TEXT("tab_release_returns_to_play"),!PC->bScoreboardVisible && !PC->bShowMouseCursor && !IsHudFocus()))return;
        if(!PC->GetPawn() && PS->RespawnAt>Match->GetServerWorldTimeSeconds()) Shot(TEXT("Deployment"));
        Next(EStep::ReopenRoster,World,.16);
        break;
    case EStep::ReopenRoster:
        SendGameKey(EKeys::Tab);
        Next(EStep::TabReopened,World);
        break;
    case EStep::TabReopened:
        if(!Require(TEXT("reopen_retains_selected_team"),PC->bScoreboardVisible && PS->Team==TargetTeam && IsHudFocus()))return;
        SlateKey(EKeys::Escape,true);SlateKey(EKeys::Escape,false);
        SlateKey(EKeys::Tab,false);
        Next(EStep::EscapeClosed,World);
        break;
    case EStep::EscapeClosed:
        if(!Require(TEXT("escape_restores_game_input"),!PC->bScoreboardVisible && !PC->bShowMouseCursor && !IsHudFocus()))return;
        SendGameKey(EKeys::Escape);
        Next(EStep::MenuOpened,World);
        break;
    case EStep::MenuOpened:
        if(!Require(TEXT("escape_opens_paused_native_menu"),PC->bMenuOpen && World->IsPaused() && PC->bShowMouseCursor && IsHudFocus()))return;
        SlateKey(EKeys::Escape,false);
        Shot(TEXT("Menu"));
        Next(EStep::OpenControls,World);
        break;
    case EStep::OpenControls:
        if(!Click(*HUD,Window,TEXT("ShowControls"),TEXT("Controls"))) return;
        Next(EStep::ControlsOpened,World);
        break;
    case EStep::ControlsOpened:
        if(!Require(TEXT("controls_retains_modal_pause"),PC->bMenuOpen && World->IsPaused() && PC->bShowMouseCursor))return;
        Shot(TEXT("Controls"));
        Next(EStep::LeaveControls,World);
        break;
    case EStep::LeaveControls:
        if(!Click(*HUD,Window,TEXT("MenuBack"),TEXT("Back"))) return;
        Next(EStep::OpenPrivate,World);
        break;
    case EStep::OpenPrivate:
        if(!Click(*HUD,Window,TEXT("PrivateMatch"),TEXT("Private match"))) return;
        Next(EStep::TryAddress,World);
        break;
    case EStep::TryAddress:
    {
        auto* Address=Cast<UEditableTextBox>(HUD->GetWidgetFromName(TEXT("HostAddress")));
        if(!Require(TEXT("private_match_form"),Address && Address->IsVisible() && World->IsPaused() &&
               HUD->GetWidgetFromName(TEXT("HostMatch"))->IsVisible() && !World->GetNetDriver()))return;
        Shot(TEXT("PrivateMatch"));
        Address->SetText(FText::FromString(TEXT("192.168.300.1:0")));
        if(!Click(*HUD,Window,TEXT("JoinMatch"),TEXT("Join match")))return;
        Next(EStep::BadAddress,World);
        break;
    }
    case EStep::BadAddress:
        if(!Require(TEXT("invalid_endpoint_keeps_solo_and_input"),World->GetNetMode()==NM_Standalone &&
                    !World->GetNetDriver() && HUD->GetWidgetFromName(TEXT("JoinMatch"))->GetIsEnabled()))return;
        if(!Click(*HUD,Window,TEXT("MenuBack"),TEXT("Back")))return;
        Next(EStep::OpenTeams,World);
        break;
    case EStep::OpenTeams:
        if(!Click(*HUD,Window,TEXT("TeamRoster"),TEXT("Team roster"))) return;
        Next(EStep::TeamsOpened,World);
        break;
    case EStep::TeamsOpened:
        if(!Require(TEXT("roster_from_menu_releases_pause"),PC->bScoreboardVisible && !PC->bMenuOpen && !World->IsPaused() && PC->bShowMouseCursor))return;
        if(!Click(*HUD,Window,TEXT("MenuBack"),TEXT("Back"))) return;
        Next(EStep::ResumeMenu,World);
        break;
    case EStep::ResumeMenu:
        if(!Require(TEXT("roster_back_returns_to_menu"),!PC->bScoreboardVisible && PC->bMenuOpen && World->IsPaused()))return;
        if(!Click(*HUD,Window,TEXT("ResumeGame"),TEXT("Resume"))) return;
        Next(EStep::Resumed,World);
        break;
    case EStep::Resumed:
        if(!Require(TEXT("resume_returns_unpaused_game_input"),!PC->bMenuOpen && !PC->bScoreboardVisible && !PC->bShowMouseCursor && !World->IsPaused() && !IsHudFocus()))return;
        Next(EStep::End,World);
        break;
    case EStep::End:
        if(Match->Phase!=3) return;
        if(!PC->bShowMouseCursor || !IsHudFocus()) return;
        if(!Require(TEXT("finished_match_owns_cursor_and_focus"),true))return;
        if(!Require(TEXT("result_scoreboard_keeps_teams_locked"),
            HUD->GetWidgetFromName(TEXT("JoinRed"))->GetVisibility()==ESlateVisibility::Collapsed &&
            HUD->GetWidgetFromName(TEXT("JoinBlue"))->GetVisibility()==ESlateVisibility::Collapsed))return;
        {
            const uint8 Before=PS->Team;
            PC->JoinTeam(1-Before);
            if(!Require(TEXT("completed_team_result_is_immutable"),PS->Team==Before))return;
        }
        Shot(TEXT("Results"));
        Next(EStep::ClickReplay,World);
        break;
    case EStep::ClickReplay:
        if(!Click(*HUD,Window,TEXT("PlayAgain"),TEXT("Play again")))return;
        if(!CameraAtSpawn(*PC,TEXT("replay_immediate_camera")))return;
        Next(EStep::ReplayClicked,World);
        break;
    case EStep::ReplayClicked:
        if(!Require(TEXT("pointer_restarts_match"),Match->Phase==1 && Match->RedScore==0 && Match->BlueScore==0 && Match->Feed.IsEmpty()))return;
        if(!Require(TEXT("replay_clock_limited_to_countdown"),
            Match->RemainingPhaseSeconds(Match->PhaseEndsAt-Match->PhaseDuration-.2)==FMath::CeilToInt32(Match->PhaseDuration)))return;
        if(!Require(TEXT("replay_returns_focus_to_game"),!PC->bShowMouseCursor && !IsHudFocus()))return;
        SendGameKey(EKeys::Escape);
        Next(EStep::QuitMenu,World);
        break;
    case EStep::QuitMenu:
        if(!Click(*HUD,Window,TEXT("QuitDesktop"),TEXT("Quit to desktop")))return;
        if(!Require(TEXT("quit_requests_native_process_exit"),IsEngineExitRequested()))return;
        Finish(true);
        break;
    case EStep::Done:
        break;
    }
}
}

void StartTempleUIInputAudit()
{
    if(!FParse::Param(FCommandLine::Get(),TEXT("RenderOffscreen"))
       || !FParse::Value(FCommandLine::Get(),TEXT("TempleUIAudit="),TempleUIAudit::File)) return;
    TempleUIAudit::File=FPaths::ConvertRelativePathToFull(TempleUIAudit::File);
    TempleUIAudit::Tick=FTSTicker::GetCoreTicker().AddTicker(FTickerDelegate::CreateLambda([](float)
    {
        if(GEngine) for(const FWorldContext& Context:GEngine->GetWorldContexts())
            if(Context.WorldType==EWorldType::Game) TempleUIAudit::Frame(Context.World());
        return TempleUIAudit::Step!=TempleUIAudit::EStep::Done;
    }));
}
void StopTempleUIInputAudit()
{
    if(TempleUIAudit::Tick.IsValid()) FTSTicker::GetCoreTicker().RemoveTicker(TempleUIAudit::Tick);
}
#endif
