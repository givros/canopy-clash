#pragma once

#include "CoreMinimal.h"
#include "Blueprint/UserWidget.h"
#include "TempleMatch.h"
#include "TempleHUD.generated.h"

class ATempleGameState;
class ATemplePlayerController;
class ATemplePlayerState;
class UButton;
class UEditableTextBox;
class UCanvasPanel;
class UCanvasPanelSlot;

/** Local, resolution-independent match instruments and actionable team roster. */
UCLASS()
class GAMEASTRAFOREST_API UTempleCombatHUD : public UUserWidget
{
    GENERATED_BODY()

public:
    explicit UTempleCombatHUD(const FObjectInitializer& ObjectInitializer);
    int32 DrawInstruments(const FGeometry& Geometry, FSlateWindowElementList& DrawList, int32 Layer) const;
#if !UE_BUILD_SHIPPING
    int32 GetRosterPageForAudit() const { return Page; }
    int32 GetRosterPageCountForAudit() const { return PageCount; }
    const FString& GetPrivateFeedbackForAudit() const { return NetworkFeedback; }
#endif

protected:
    virtual TSharedRef<SWidget> RebuildWidget() override;
    virtual void NativeOnInitialized() override;
    virtual void NativeTick(const FGeometry& Geometry, float DeltaSeconds) override;
    virtual FReply NativeOnPreviewKeyDown(const FGeometry& Geometry, const FKeyEvent& Event) override;
    virtual FReply NativeOnKeyUp(const FGeometry& Geometry, const FKeyEvent& Event) override;
    virtual FReply NativeOnMouseWheel(const FGeometry& Geometry, const FPointerEvent& Event) override;
    virtual FReply NativeOnMouseButtonDown(const FGeometry& Geometry, const FPointerEvent& Event) override;
    virtual FReply NativeOnMouseButtonUp(const FGeometry& Geometry, const FPointerEvent& Event) override;

private:
    UPROPERTY(Transient) TObjectPtr<UButton> RedButton;
    UPROPERTY(Transient) TObjectPtr<UButton> BlueButton;
    UPROPERTY(Transient) TObjectPtr<UButton> ReplayButton;
    UPROPERTY(Transient) TObjectPtr<UButton> ResumeButton;
    UPROPERTY(Transient) TObjectPtr<UButton> TeamsButton;
    UPROPERTY(Transient) TObjectPtr<UButton> ControlsButton;
    UPROPERTY(Transient) TObjectPtr<UButton> PrivateButton;
    UPROPERTY(Transient) TObjectPtr<UButton> HostButton;
    UPROPERTY(Transient) TObjectPtr<UButton> ConnectButton;
    UPROPERTY(Transient) TObjectPtr<UButton> LeaveButton;
    UPROPERTY(Transient) TObjectPtr<UEditableTextBox> AddressBox;
    UPROPERTY(Transient) TObjectPtr<UButton> QuitButton;
    UPROPERTY(Transient) TObjectPtr<UButton> BackButton;
    UPROPERTY(Transient) TObjectPtr<UCanvasPanel> Actions;

    UFUNCTION() void JoinRed();
    UFUNCTION() void JoinBlue();
    UFUNCTION() void Replay();
    UFUNCTION() void Resume();
    UFUNCTION() void MenuTeams();
    UFUNCTION() void MenuControls();
    UFUNCTION() void MenuPrivate();
    UFUNCTION() void HostPrivate();
    UFUNCTION() void JoinPrivate();
    UFUNCTION() void LeavePrivate();
    UFUNCTION() void MenuBack();
    UFUNCTION() void QuitDesktop();
    UButton* MakeAction(FName Name, const FString& Text, const FLinearColor& Tint);
    void UpdateRoster(const ATempleGameState* Match);
    void ArrangeActions(const FVector2D& Size, const ATempleGameState* Match, const ATemplePlayerState* Local, bool bShow, bool bMenu);
    void TurnPage(int32 Delta);
    static float InterfaceScale(FVector2D Size);
    TArray<FTempleStanding> Rosters[2];
    int32 Page = 0;
    int32 PageCount = 1;
    double NextRosterUpdate = 0.;
    bool bModalOpen = false;
    bool bPreviousResult = false;
    bool bPreviousMenu = false;
    bool bControlsPage = false;
    bool bPrivatePage = false;
    bool bConnecting = false;
    FString HostAddress;
    FString NetworkFeedback;
    bool bRosterFromMenu = false;
    uint8 PreviousTeam = 255;
    FVector2D LastSize = FVector2D::ZeroVector;
    float SmoothedSpread = 5.f;
    int32 PreviousPhase = INDEX_NONE;
    float GoUntil = -1.f;
    float SpawnHintUntil = -1.f;
    TWeakObjectPtr<APawn> LastSpawn;
};
