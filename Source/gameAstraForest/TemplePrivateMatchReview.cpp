#if !UE_BUILD_SHIPPING
#include "TempleGameInstance.h"
#include "TempleHUD.h"
#include "TempleMatch.h"
#include "Blueprint/WidgetBlueprintLibrary.h"
#include "Components/EditableTextBox.h"
#include "Containers/Ticker.h"
#include "Engine/Engine.h"
#include "Engine/GameViewportClient.h"
#include "Framework/Application/SlateApplication.h"
#include "GameFramework/InputDeviceLibrary.h"
#include "Input/HittestGrid.h"
#include "InputKeyEventArgs.h"
#include "Layout/WidgetPath.h"
#include "Misc/CommandLine.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "UnrealClient.h"
#include "Widgets/SWindow.h"

namespace TemplePrivateReview
{
FString File;
FString PreviousCommand;
FString Response;
FString PreviousStatus;
FTSTicker::FDelegateHandle Ticker;

bool Visible(UTempleCombatHUD& HUD, const TCHAR* Name)
{
    UWidget* Widget = HUD.GetWidgetFromName(Name);
    return Widget && Widget->IsVisible() && Widget->GetIsEnabled();
}

bool PressWidget(UTempleCombatHUD& HUD, SWindow& Window, FName Name)
{
    UWidget* Widget = HUD.GetWidgetFromName(Name);
    if (!Widget || !Widget->IsVisible() || !Widget->GetIsEnabled()) return false;
    const TSharedPtr<SWidget> Native = Widget->GetCachedWidget();
    if (!Native) return false;
    const FGeometry Geometry = Widget->GetCachedGeometry();
    const FVector2D Point = Geometry.LocalToAbsolute(Geometry.GetLocalSize() * .5);
    auto Hits = Window.GetHittestGrid().GetBubblePath(Point, 0.f, false, 0);
    if (Hits.IsEmpty()) return false;
    const FWidgetPath Path(MakeArrayView(Hits));
    if (!Path.ContainsWidget(Native.Get())) return false;
    const TSet<FKey> Empty;
    TSet<FKey> Pressed;
    Pressed.Add(EKeys::LeftMouseButton);
    const int32 Pointer = FSlateApplication::CursorPointerIndex;
    const FPointerEvent Move(0, Pointer, Point, Point, Empty, FKey(), 0, FModifierKeysState());
    const FPointerEvent Down(0, Pointer, Point, Point, Pressed, EKeys::LeftMouseButton, 0, FModifierKeysState());
    const FPointerEvent Up(0, Pointer, Point, Point, Empty, EKeys::LeftMouseButton, 0, FModifierKeysState());
    auto& App = FSlateApplication::Get();
    App.RoutePointerMoveEvent(Path, Move, false);
    const bool bDown = App.RoutePointerDownEvent(Path, Down).IsEventHandled();
    const bool bUp = App.RoutePointerUpEvent(Path, Up).IsEventHandled();
    return bDown && bUp;
}

bool Perform(const FString& Action, const FString& Argument, ATemplePlayerController& PC,
             UGameViewportClient& Viewport, UTempleCombatHUD& HUD)
{
    if (Action == TEXT("escape"))
    {
        const auto Device = UInputDeviceLibrary::GetPrimaryInputDeviceForUser(PC.GetPlatformUserId());
        Viewport.InputKey(FInputKeyEventArgs::CreateSimulated(
            EKeys::Escape, IE_Pressed, 1.f, -1, Device, false, Viewport.Viewport));
        Viewport.InputKey(FInputKeyEventArgs::CreateSimulated(EKeys::Escape, IE_Released, 0.f, -1, Device, false, Viewport.Viewport));
        return true; // The viewport dispatches player BindAction events on the next input frame.
    }
    if (Action == TEXT("type"))
    {
        if (!PressWidget(HUD, *Viewport.GetWindow(), TEXT("HostAddress"))) return false;
        auto& App = FSlateApplication::Get();
        const FModifierKeysState Ctrl(false, false, true, false, false, false, false, false, false);
        const FKeyEvent SelectAll(EKeys::A, Ctrl, 0, false, 0, 0);
        App.ProcessKeyDownEvent(SelectAll);
        App.ProcessKeyUpEvent(SelectAll);
        for (const TCHAR Character : Argument) App.OnKeyChar(Character, false);
        const auto* Box = Cast<UEditableTextBox>(HUD.GetWidgetFromName(TEXT("HostAddress")));
        return Box && Box->GetText().ToString() == Argument;
    }
    if (Action == TEXT("click"))
    {
        if (Argument != TEXT("PrivateMatch") && Argument != TEXT("HostMatch") && Argument != TEXT("JoinMatch")
            && Argument != TEXT("LeaveMatch") && Argument != TEXT("MenuBack") && Argument != TEXT("ResumeGame")) return false;
        return PressWidget(HUD, *Viewport.GetWindow(), FName(*Argument));
    }
    if (Action == TEXT("capture") && !Argument.IsEmpty() && FPaths::GetCleanFilename(Argument) == Argument)
    {
        FScreenshotRequest::RequestScreenshot(FPaths::Combine(FPaths::GetPath(File), Argument + TEXT(".png")), true, false);
        return true;
    }
    if (Action == TEXT("stop"))
    {
        FPlatformMisc::RequestExit(false);
        return true;
    }
    return false;
}

void Frame(UWorld& World)
{
    if (!World.IsGameWorld() || !World.GetMapName().Contains(TEXT("L_CanopyDeathmatch")) || !FSlateApplication::IsInitialized()) return;
    auto* PC = Cast<ATemplePlayerController>(World.GetFirstPlayerController());
    auto* Match = World.GetGameState<ATempleGameState>();
    auto* Instance = World.GetGameInstance<UTempleGameInstance>();
    auto* Viewport = World.GetGameViewport();
    if (!PC || !PC->IsLocalController() || !PC->GetPlayerState<ATemplePlayerState>() || !Match || !Instance || !Viewport || !Viewport->GetWindow()) return;
    TArray<UUserWidget*> Widgets;
    UWidgetBlueprintLibrary::GetAllWidgetsOfClass(&World, Widgets, UTempleCombatHUD::StaticClass(), true);
    UTempleCombatHUD* HUD = nullptr;
    for (UUserWidget* Widget : Widgets) if (Widget->GetOwningPlayer() == PC) HUD = Cast<UTempleCombatHUD>(Widget);
    if (!HUD || !HUD->GetCachedWidget()) return;

    FString Command;
    if (FFileHelper::LoadFileToString(Command, *File) && Command != PreviousCommand)
    {
        TArray<FString> Parts;
        Command.TrimStartAndEnd().ParseIntoArray(Parts, TEXT("|"), false);
        if (Parts.Num() >= 2)
        {
            PreviousCommand = Command;
            const bool bOK = Perform(Parts[1], Parts.Num() > 2 ? Parts[2] : FString(), *PC, *Viewport, *HUD);
            Response = FString::Printf(TEXT("%s:%s"), *Parts[0], bOK ? TEXT("ok") : TEXT("failed"));
        }
    }
    int32 Humans = 0;
    for (APlayerState* State : Match->PlayerArray) if (State && !State->IsABot()) ++Humans;
    const auto* Address = Cast<UEditableTextBox>(HUD->GetWidgetFromName(TEXT("HostAddress")));
    const FString EnteredAddress = Address ? Address->GetText().ToString() : FString();
    const FString Status = FString::Printf(
        TEXT("%s|%d|%s|%d|%d|%d|%d|%d|%d|%d|%d|%d|%s|%d|%s"),
        *Response, int32(World.GetNetMode()), *Instance->CurrentEndpoint(), Match->PlayerArray.Num(), Humans,
        int32(PC->bMenuOpen), int32(Visible(*HUD, TEXT("PrivateMatch"))), int32(Visible(*HUD, TEXT("HostMatch"))),
        int32(Visible(*HUD, TEXT("JoinMatch"))), int32(Visible(*HUD, TEXT("LeaveMatch"))), int32(World.IsPaused()),
        int32(PC->bShowMouseCursor), *HUD->GetPrivateFeedbackForAudit(), Match->Phase, *EnteredAddress);
    if (Status != PreviousStatus)
    {
        FFileHelper::SaveStringToFile(Status, *(File + TEXT(".state")), FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
        UE_LOG(LogTemp, Display, TEXT("TemplePrivateAudit %s"), *Status);
        PreviousStatus = Status;
    }
}
}

void StartTemplePrivateReview()
{
    if (!FParse::Param(FCommandLine::Get(), TEXT("RenderOffscreen"))
        || !FParse::Value(FCommandLine::Get(), TEXT("TemplePrivateAudit="), TemplePrivateReview::File)) return;
    TemplePrivateReview::Ticker = FTSTicker::GetCoreTicker().AddTicker(FTickerDelegate::CreateLambda([](float) {
        if (GEngine) for (const FWorldContext& Context : GEngine->GetWorldContexts())
            if (Context.WorldType == EWorldType::Game && Context.World()) TemplePrivateReview::Frame(*Context.World());
        return !IsEngineExitRequested();
    }), .16f);
}

void StopTemplePrivateReview()
{
    if (TemplePrivateReview::Ticker.IsValid()) FTSTicker::GetCoreTicker().RemoveTicker(TemplePrivateReview::Ticker);
}
#endif
