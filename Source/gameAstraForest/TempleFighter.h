#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Character.h"
#include "Navigation/CrowdAgentInterface.h"
#include "TempleFighter.generated.h"

class UAnimSequence;
class UCameraComponent;
class UChildActorComponent;
class UInputAction;
class UInputMappingContext;
class UMaterialInstanceDynamic;
class UMaterialInterface;
class UNiagaraSystem;
class UTempleMuzzleLight;
class UNiagaraComponent;
class USkeletalMeshComponent;
class UStaticMeshComponent;
class UStaticMesh;
class USoundAttenuation;
class USoundBase;
class UTempleRifleComponent;
class UTempleMagazinePresentation;
struct FInputActionValue;
struct FStreamableHandle;

UCLASS()
class GAMEASTRAFOREST_API ATempleFighter : public ACharacter, public ICrowdAgentInterface
{
    GENERATED_BODY()
public:
    ATempleFighter();
    virtual void Tick(float DeltaSeconds) override;
    virtual float TakeDamage(float Amount, const FDamageEvent& Event, AController* InstigatorController, AActor* Causer) override;
    virtual void GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const override;
    virtual void PawnClientRestart() override;
    virtual void PossessedBy(AController* NewController) override;
    virtual void UnPossessed() override;
    virtual FVector GetCrowdAgentLocation() const override;
    virtual FVector GetCrowdAgentVelocity() const override { return GetVelocity(); }
    virtual void GetCrowdAgentCollisions(float& Radius,float& HalfHeight) const override;
    virtual void GetActorEyesViewPoint(FVector& Location, FRotator& Rotation) const override;

    UFUNCTION(BlueprintCallable) void SetTeam(uint8 InTeam);
    UFUNCTION(BlueprintPure) uint8 GetTeam() const { return Team; }
    UFUNCTION(BlueprintPure, Category="Bots") FName GetBotAppearanceName() const;
    static int32 FindBotAppearanceSlot(FName Identity);
    UFUNCTION(BlueprintPure, Category="Bots") USkeletalMeshComponent* GetBotPresentationBody() const { return BotPresentationBody; }
    UFUNCTION(BlueprintPure) bool IsAlive() const { return Health > 0.f; }
    UFUNCTION(BlueprintPure) float GetHealth() const { return Health; }
    UFUNCTION(BlueprintPure) float GetMaxHealth() const { return MaxHealth; }
    UFUNCTION(BlueprintPure) int32 GetMagazineAmmo() const;
    UFUNCTION(BlueprintPure) int32 GetReserveAmmo() const;
    UFUNCTION(BlueprintPure) int32 GetMagazineCapacity() const;
    UFUNCTION(BlueprintPure) bool IsAiming() const { return bAiming; }
    UFUNCTION(BlueprintPure) bool IsReloading() const;
    UFUNCTION(BlueprintPure) float GetReloadAlpha() const;
    UFUNCTION(BlueprintPure) bool IsSpawnProtected() const;
    UFUNCTION(BlueprintPure) float GetLocalHitTime() const { return LocalHitTime; }
    UFUNCTION(BlueprintPure) bool GetLocalHitWasKill() const { return bLastHitKilled; }
    UFUNCTION(BlueprintPure) float GetLastDamageTime() const { return LastDamageTime; }
    UFUNCTION(BlueprintPure) FVector GetLastDamageDirection() const { return LastDamageDirection; }
    UFUNCTION(BlueprintPure) float GetLocalShotTime() const { return LocalShotTime; }
    UFUNCTION(BlueprintCallable) void SetTriggerHeld(bool bPressed);
    UFUNCTION(BlueprintCallable) void SetAiming(bool bPressed);
    UFUNCTION(BlueprintCallable) void StartReload();
    UFUNCTION(BlueprintCallable) void GrantSpawnProtection(float Seconds);
    UFUNCTION(BlueprintCallable) void Eliminate(AController* Killer);

    bool CombatActive() const;
    bool IsFirstPersonViewSettled() const;
    bool HasRecentServerShot(float Now) const { return Now-LastServerShotTime<6.f; }
    float ServerClock() const;
    FVector WorldMuzzle() const;
    void FiredOnServer();
    void PlayShotPresentation(const FRotator& Heading);
    UFUNCTION(NetMulticast, Unreliable) void MulticastShot(FVector_NetQuantize Destination, FVector_NetQuantizeNormal Normal, bool bImpact, bool bFighterImpact, int32 PullId, int32 ShotIndex);
    UFUNCTION(NetMulticast, Reliable) void MulticastReload();
    UFUNCTION(Client, Unreliable) void ClientConfirmHit(bool bEliminated);
    UFUNCTION(Client, Unreliable) void ClientDamageFeedback(FVector_NetQuantizeNormal Direction);

protected:
    virtual void BeginPlay() override;
    virtual void SetupPlayerInputComponent(UInputComponent* Input) override;
    virtual void EndPlay(const EEndPlayReason::Type Reason) override;

    UPROPERTY(VisibleAnywhere,BlueprintReadOnly,Category="Fighter") TObjectPtr<UCameraComponent> FirstPersonCamera;
    UPROPERTY(VisibleAnywhere,BlueprintReadOnly,Category="Fighter") TObjectPtr<USkeletalMeshComponent> ViewArms;
    UPROPERTY(VisibleAnywhere,BlueprintReadOnly,Category="Fighter") TObjectPtr<USkeletalMeshComponent> ViewRifle;
    UPROPERTY(VisibleAnywhere,BlueprintReadOnly,Category="Fighter") TObjectPtr<USkeletalMeshComponent> WorldRifle;
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category="Bots") TObjectPtr<UChildActorComponent> BotPresentation;
    UPROPERTY(EditDefaultsOnly, Category="Bots") TArray<TSoftClassPtr<AActor>> BotAppearanceClasses;
    UPROPERTY() TObjectPtr<UTempleMagazinePresentation> ViewMagazine;
    UPROPERTY() TObjectPtr<UTempleMagazinePresentation> WorldMagazine;
    UPROPERTY(VisibleAnywhere,BlueprintReadOnly,Category="Fighter") TObjectPtr<UTempleRifleComponent> Rifle;
    UPROPERTY(EditDefaultsOnly,Category="Fighter",meta=(ClampMin="1")) float MaxHealth=100.f;
    UPROPERTY(EditDefaultsOnly,Category="View") float HipFov=90.f;
    UPROPERTY(EditDefaultsOnly,Category="View") float AimFov=64.f;

private:
    void LeavePlayerCrowd();
    bool bPlayerCrowdRegistered=false;
    UPROPERTY(ReplicatedUsing=OnRep_Team) uint8 Team=255;
    UPROPERTY(ReplicatedUsing=OnRep_BotAppearance) uint8 BotAppearance = 255;
    UPROPERTY(Transient) TObjectPtr<USkeletalMeshComponent> BotPresentationBody;
    UPROPERTY() TObjectPtr<UStaticMesh> BotArmbandMesh;
    UPROPERTY() TObjectPtr<UMaterialInterface> BotArmbandMaterial;
    UPROPERTY(Transient) TObjectPtr<UMaterialInstanceDynamic> BotArmbandPaint;
    TSharedPtr<FStreamableHandle> BotAppearanceLoad;
    FTransform AuthoredWorldRifleOffset = FTransform::Identity;
    void InitializeBotAppearances();
    void SelectBotAppearance(AController* NewController);
    void FinishBotAppearance();
    void AttachBotArmband(AActor* Model, USkeletalMeshComponent* Body);
    void AttachBotRifle(USkeletalMeshComponent* Body);
    void CancelBotAppearanceLoad();
    UFUNCTION() void OnRep_BotAppearance();
    UPROPERTY(ReplicatedUsing=OnRep_Health) float Health=100.f;
    UPROPERTY(Replicated) float ProtectedUntil=0.f;
    UPROPERTY(ReplicatedUsing=OnRep_Pace) bool bAiming=false;
    UPROPERTY(ReplicatedUsing=OnRep_Pace) bool bSprinting=false;
    UPROPERTY() TObjectPtr<UAnimSequence> RifleFire;
    UPROPERTY() TObjectPtr<UAnimSequence> RifleEquip;
    UPROPERTY() TObjectPtr<UAnimSequence> RifleReload;
    UPROPERTY() TObjectPtr<UAnimSequence> DeathClip;
    UPROPERTY() TObjectPtr<USoundBase> ShotSound;
    UPROPERTY() TObjectPtr<USoundBase> ReloadSound;
    UPROPERTY() TObjectPtr<USoundBase> ConfirmSound;
    UPROPERTY() TObjectPtr<USoundAttenuation> Attenuation;
    UPROPERTY() TObjectPtr<UTempleMuzzleLight> MuzzleFlash;
    UPROPERTY() TObjectPtr<UNiagaraComponent> MuzzleBurst;
    UPROPERTY(EditDefaultsOnly,Category="Feedback") TSoftObjectPtr<UNiagaraSystem> FlashParticleAsset;
    UPROPERTY(EditDefaultsOnly,Category="Feedback") TSoftObjectPtr<UNiagaraSystem> ImpactParticleAsset;
    UPROPERTY(Transient) TObjectPtr<UNiagaraSystem> ImpactParticles;
    UPROPERTY() TObjectPtr<UStaticMeshComponent> TraceMesh;
    UPROPERTY() TObjectPtr<UInputAction> MoveAction;
    UPROPERTY() TObjectPtr<UInputAction> LookAction;
    UPROPERTY() TObjectPtr<UInputAction> MouseAction;
    UPROPERTY() TObjectPtr<UInputAction> JumpAction;
    UPROPERTY() TArray<TObjectPtr<UInputMappingContext>> Contexts;
    UPROPERTY() TArray<TObjectPtr<UMaterialInstanceDynamic>> TeamMaterials;
    float LocalHitTime=-1000.f;
    float LastDamageTime=-1000.f;
    float LocalShotTime=-1000.f;
    float LastServerShotTime=-1000.f;
    float AimAlpha=0.f;
    float Kick=0.f;
    float RecoilPitch=0.f;
    float RecoilYaw=0.f;
    float TraceUntil=0.f;
    float NextViewReport=0.f;
    FVector LastDamageDirection=FVector::ZeroVector;
    FVector ViewIdleMuzzle=FVector::ZeroVector;
    FQuat HipCorrection=FQuat::Identity;
    FQuat SightCorrection=FQuat::Identity;
    bool bLastHitKilled=false;
    bool bShowingDeath=false;
    bool bCalibratedView=false;
    bool bViewWasActive=false;
    float ViewPoseStartedAt=0.f;
    float ViewEquipEndsAt=0.f;
    void Move(const FInputActionValue& Value);
    void MouseLook(const FInputActionValue& Value);
    void PadLook(const FInputActionValue& Value);
    void StartFireInput(); void StopFireInput();
    void JumpInput();
    void ReloadInput();
    bool MayUseInput(bool bAllowCountdown=false) const;
    void OnApplicationActive(bool bActive);
    void StartADS(); void StopADS();
    void SprintOn(); void SprintOff();
    void CrouchOn(); void CrouchOff();
    void SetSprinting(bool bPressed);
    void AddContexts();
    void RefreshPace();
    void ShowDeath();
    void RefreshView(float DeltaSeconds);
    void PlayViewAnimation(UAnimSequence* Sequence,float Duration,float Progress=0.f);
    UFUNCTION() void OnRep_Team();
    UFUNCTION() void OnRep_Health();
    UFUNCTION() void OnRep_Pace();
    FVector PresentationMuzzle() const;
    UFUNCTION(Server,Reliable) void ServerSetTrigger(bool bPressed,int32 PullId,FVector_NetQuantizeNormal ViewDirection);
    UFUNCTION(Client,Reliable) void ClientTriggerClosed(int32 PullId,int32 AuthoritativeAmmo);
    UFUNCTION(Client,Reliable) void ClientReloadDeclined();
    UFUNCTION(Server,Reliable) void ServerSetAiming(bool bPressed);
    UFUNCTION(Server,Reliable) void ServerSetSprinting(bool bPressed);
    UFUNCTION(Server,Reliable) void ServerStartReload();
};
