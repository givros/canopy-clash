#pragma once
#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "GameFramework/GameStateBase.h"
#include "GameFramework/PlayerState.h"
#include "GameFramework/PlayerController.h"
#include "TempleMatch.generated.h"

class ATempleFighter;
class ATempleBotController;
class APlayerStart;
class UTempleCombatHUD;

USTRUCT(BlueprintType)
struct FTempleFeedEntry
{
    GENERATED_BODY()
    UPROPERTY(BlueprintReadOnly) FString Killer;
    UPROPERTY(BlueprintReadOnly) FString Victim;
    UPROPERTY(BlueprintReadOnly) uint8 KillerTeam = 255;
    UPROPERTY(BlueprintReadOnly) uint8 VictimTeam = 255;
    UPROPERTY(BlueprintReadOnly) int32 Serial = 0;
    UPROPERTY(BlueprintReadOnly) float ServerTime = 0;
};

UCLASS()
class GAMEASTRAFOREST_API ATemplePlayerState : public APlayerState
{
    GENERATED_BODY()
public:
    UPROPERTY(Replicated, BlueprintReadOnly) uint8 Team = 255;
    UPROPERTY(Replicated, BlueprintReadOnly) int32 Kills = 0;
    UPROPERTY(Replicated, BlueprintReadOnly) int32 Deaths = 0;
    UPROPERTY(Replicated, BlueprintReadOnly) float RespawnAt = 0;
    virtual void GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& Out) const override;
};

USTRUCT(BlueprintType)
struct FTempleStanding
{
    GENERATED_BODY()
    UPROPERTY(BlueprintReadOnly) FString Name;
    UPROPERTY(BlueprintReadOnly) int32 PlayerId = INDEX_NONE;
    UPROPERTY(BlueprintReadOnly) uint8 Team = 255;
    UPROPERTY(BlueprintReadOnly) int32 Kills = 0;
    UPROPERTY(BlueprintReadOnly) int32 Deaths = 0;
    FTempleStanding()=default;
    explicit FTempleStanding(const ATemplePlayerState& Player)
        : Name(Player.GetPlayerName()),PlayerId(Player.GetPlayerId()),Team(Player.Team),Kills(Player.Kills),Deaths(Player.Deaths) {}
};

UCLASS()
class GAMEASTRAFOREST_API ATempleGameState : public AGameStateBase
{
    GENERATED_BODY()
public:
    UPROPERTY(Replicated, BlueprintReadOnly) int32 RedScore = 0;
    UPROPERTY(Replicated, BlueprintReadOnly) int32 BlueScore = 0;
    UPROPERTY(Replicated, BlueprintReadOnly) int32 ScoreLimit = 50;
    UPROPERTY(Replicated, BlueprintReadOnly) float RespawnDelay = 3.f;
    UPROPERTY(Replicated, BlueprintReadOnly) int32 Phase = 0;
    UPROPERTY(Replicated, BlueprintReadOnly) double PhaseEndsAt = 0;
    UPROPERTY(Replicated, BlueprintReadOnly) float PhaseDuration = 0;
    UPROPERTY(Replicated, BlueprintReadOnly) uint8 WinnerTeam = 255;
    UPROPERTY(Replicated, BlueprintReadOnly) TArray<FTempleFeedEntry> Feed;
    UPROPERTY(Replicated, BlueprintReadOnly) TArray<FTempleStanding> FinalStandings;
    void StartPhase(int32 NewPhase, float Duration);
    int32 RemainingPhaseSeconds(double ServerNow) const;
    virtual void GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& Out) const override;
};

UCLASS()
class GAMEASTRAFOREST_API ATemplePlayerController : public APlayerController
{
    GENERATED_BODY()
public:
    UPROPERTY(BlueprintReadOnly) bool bScoreboardVisible = false;
    UPROPERTY(BlueprintReadOnly) bool bMenuOpen = false;
    UFUNCTION(BlueprintCallable) void JoinTeam(int32 Team);
    UFUNCTION(BlueprintCallable) void ReplayMatch();
    UFUNCTION(BlueprintCallable) void SetScoreboardVisible(bool bVisible);
    UFUNCTION(BlueprintCallable) void SetMenuOpen(bool bOpen);
    UFUNCTION(BlueprintCallable) void ToggleMenu();
    UFUNCTION(BlueprintCallable) void OpenTeamsFromMenu();
    UFUNCTION(BlueprintCallable) void QuitGame();
    UFUNCTION(Server,Reliable) void ServerJoinTeam(int32 Team);
    UFUNCTION(Server,Reliable) void ServerReplayMatch();
    virtual void BeginPlay() override;
    virtual void SetupInputComponent() override;
    virtual void PlayerTick(float DeltaTime) override;
    virtual void ClientSetRotation_Implementation(FRotator NewRotation,bool bResetCamera) override;
private:
    UPROPERTY(Transient) TObjectPtr<UTempleCombatHUD> Overlay;
    bool bHasInteractiveHUD = false;
    void RefreshInteraction();
    void OpenScoreboard();
    void SelectRed();
    void SelectBlue();
};

UCLASS(Blueprintable, Config=Game)
class GAMEASTRAFOREST_API ATempleMatchMode : public AGameModeBase
{
    GENERATED_BODY()
public:
    ATempleMatchMode();
    UPROPERTY(Config,EditDefaultsOnly,BlueprintReadOnly,Category="Rules") int32 TeamSize = 5;
    UPROPERTY(Config,EditDefaultsOnly,BlueprintReadOnly,Category="Rules") int32 ScoreTarget = 50;
    UPROPERTY(Config,EditDefaultsOnly,BlueprintReadOnly,Category="Rules") float MatchDuration = 600;
    UPROPERTY(Config,EditDefaultsOnly,BlueprintReadOnly,Category="Rules") float CountdownSeconds = 3;
    UPROPERTY(Config,EditDefaultsOnly,BlueprintReadOnly,Category="Rules") float RespawnDelay = 3;
    UPROPERTY(Config,EditDefaultsOnly,BlueprintReadOnly,Category="Rules") float SpawnProtectionSeconds = 2.75f;
    UPROPERTY(Config,EditDefaultsOnly,BlueprintReadOnly,Category="Rules") bool bFriendlyFire = false;
    UPROPERTY(EditDefaultsOnly,BlueprintReadOnly,Category="Teams") TSubclassOf<ATempleBotController> BotControllerClass;
    UFUNCTION(BlueprintPure) bool IsCombatActive() const;
    void HandleElimination(ATempleFighter* Victim, AController* Killer);
    FVector GetPatrolGoal(uint8 Team,FVector From) const;
    bool GetLaneGoal(uint8 Team,int32 Lane,FVector From,int32& Station,int32& Direction,FVector& Destination) const;
    bool IsEnemySafeZone(uint8 Team,const FVector& Point) const;
    void SwitchTeam(ATemplePlayerController* Human,uint8 Team);
    void Replay();
    virtual void InitGame(const FString& Map,const FString& Options,FString& Error) override;
    virtual void StartPlay() override;
    virtual void PostLogin(APlayerController* NewPlayer) override;
    virtual void ChangeName(AController* Controller, const FString& NewName, bool bNameChange) override;
    virtual void Logout(AController* Exiting) override;
    virtual void RestartPlayer(AController* Player) override;
    virtual AActor* ChoosePlayerStart_Implementation(AController* Player) override;
    virtual void Tick(float DeltaSeconds) override;
private:
    void DiscoverArena();
    void EnsureRosters();
    void StartRound();
    void EndRound();
    void RemovePawn(AController* Controller);
    void RetireBot(AController* Bot);
    uint8 SmallerTeam() const;
    double NextPopulationCheck = 0;
    int32 FeedSerial = 0;
    int32 BotSerial = 0;
    int32 DuelBotSlot = INDEX_NONE;
    bool bReady = false;
    TArray<TWeakObjectPtr<APlayerStart>> Starts[2];
    TArray<FVector> PatrolNodes;
    TArray<FVector> PatrolLanes[4];
    FVector BaseCenters[2] = {};
    TMap<TWeakObjectPtr<AController>,double> LastTeamChange;
};
