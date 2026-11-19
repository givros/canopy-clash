#include "TempleFighter.h"
#include "TempleRifleComponent.h"
#include "TempleRifleMesh.h"
#include "TempleMagazinePresentation.h"
#include "TempleMuzzleLight.h"
#include "TempleFootstepComponent.h"
#include "TempleMatch.h"
#include "Animation/AnimInstance.h"
#include "Animation/AnimSequence.h"
#include "Camera/CameraComponent.h"
#include "Components/CapsuleComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/DamageEvents.h"
#include "Engine/LocalPlayer.h"
#include "Engine/SkeletalMesh.h"
#include "Engine/StaticMesh.h"
#include "Framework/Application/SlateApplication.h"
#include "NiagaraFunctionLibrary.h"
#include "NiagaraComponent.h"
#include "Navigation/CrowdManager.h"
#include "NiagaraSystem.h"
#include "EnhancedInputComponent.h"
#include "EnhancedInputSubsystems.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/GameStateBase.h"
#include "GameFramework/PlayerController.h"
#include "InputAction.h"
#include "InputMappingContext.h"
#include "InputCoreTypes.h"
#include "Kismet/GameplayStatics.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Misc/CommandLine.h"
#include "Net/UnrealNetwork.h"
#include "Sound/SoundAttenuation.h"
#include "Sound/SoundBase.h"
#include "UObject/ConstructorHelpers.h"
#if !UE_BUILD_SHIPPING
void UpdateTempleBodyReview(ATempleFighter* Fighter);
#endif

namespace
{
template<class T> T* Asset(const TCHAR* Path)
{
    return ConstructorHelpers::FObjectFinder<T>(Path).Object;
}
const FName Grip(TEXT("HandGrip_R"));
const FName Muzzle(TEXT("Muzzle"));
const FVector ViewRest(-13,0,-148);
constexpr float ViewEquipSeconds=.52f;
}

ATempleFighter::ATempleFighter()
{
    PrimaryActorTick.bCanEverTick=true;
    bReplicates=true;
    GetCapsuleComponent()->InitCapsuleSize(34,96);
    GetCapsuleComponent()->SetCollisionResponseToChannel(ECC_Visibility,ECR_Block);
    BaseEyeHeight=66.f;
    CrouchedEyeHeight=40.f;
    UCharacterMovementComponent* MoveComp=GetCharacterMovement();
    MoveComp->GetNavAgentPropertiesRef().bCanCrouch=true;
    MoveComp->MaxWalkSpeed=510.f;
    MoveComp->MaxWalkSpeedCrouched=235.f;
    MoveComp->MaxAcceleration=3000.f;
    MoveComp->BrakingDecelerationWalking=2200.f;
    MoveComp->JumpZVelocity=470.f;
    MoveComp->AirControl=.4f;
    bUseControllerRotationYaw=true;

    USkeletalMesh* Manny=Asset<USkeletalMesh>(TEXT("/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple.SKM_Manny_Simple"));
    USkeletalMesh* Weapon=Asset<USkeletalMesh>(TEXT("/Game/TempleTDM/Presentation/SKM_CanopyReceiver.SKM_CanopyReceiver"));
    GetMesh()->SetSkeletalMeshAsset(Manny);
    GetMesh()->SetRelativeLocationAndRotation(FVector(-10,0,-96),FRotator(0,-90,0));
    GetMesh()->SetOwnerNoSee(true);
    GetMesh()->bCastHiddenShadow=true;
    GetMesh()->SetCollisionProfileName(TEXT("NoCollision"));
    GetMesh()->VisibilityBasedAnimTickOption=EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
    const ConstructorHelpers::FClassFinder<UAnimInstance> BodyPose(TEXT("/Game/TempleTDM/Animation/ABP_TempleBody"));
    if (BodyPose.Class) GetMesh()->SetAnimInstanceClass(BodyPose.Class);
    InitializeBotAppearances();

    FirstPersonCamera=CreateDefaultSubobject<UCameraComponent>(TEXT("FirstPersonCamera"));
    FirstPersonCamera->SetupAttachment(GetCapsuleComponent());
    FirstPersonCamera->SetRelativeLocation(FVector(0,0,BaseEyeHeight));
    FirstPersonCamera->bUsePawnControlRotation=true;
    FirstPersonCamera->SetFieldOfView(HipFov);
    ViewArms=CreateDefaultSubobject<USkeletalMeshComponent>(TEXT("ViewArms"));
    ViewArms->SetupAttachment(FirstPersonCamera);
    ViewArms->SetRelativeLocationAndRotation(ViewRest,FRotator(0,-90,0));
    ViewArms->SetSkeletalMeshAsset(Asset<USkeletalMesh>(TEXT("/Game/TempleTDM/Animation/SKM_TempleArms.SKM_TempleArms")));
    ViewArms->VisibilityBasedAnimTickOption=EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
    const ConstructorHelpers::FClassFinder<UAnimInstance> ViewPose(TEXT("/Game/TempleTDM/Animation/ABP_TempleArms"));
    if (ViewPose.Class) ViewArms->SetAnimInstanceClass(ViewPose.Class);
    ViewArms->SetOnlyOwnerSee(true);
    ViewArms->SetCastShadow(false);
    ViewArms->SetCollisionProfileName(TEXT("NoCollision"));
    ViewArms->FirstPersonPrimitiveType=EFirstPersonPrimitiveType::FirstPerson;
    FirstPersonCamera->bEnableFirstPersonScale=true;
    FirstPersonCamera->FirstPersonScale=.58f;
    FirstPersonCamera->bEnableFirstPersonFieldOfView=true;
    FirstPersonCamera->FirstPersonFieldOfView=HipFov;
    ViewRifle=CreateDefaultSubobject<USkeletalMeshComponent>(TEXT("ViewCarbine"));
    ViewRifle->SetupAttachment(ViewArms,Grip);
    ViewRifle->SetSkeletalMeshAsset(Weapon);
    ViewRifle->VisibilityBasedAnimTickOption=EVisibilityBasedAnimTickOption::AlwaysTickPoseAndRefreshBones;
    ViewRifle->SetOnlyOwnerSee(true);
    ViewRifle->SetCastShadow(false);
    ViewRifle->FirstPersonPrimitiveType=EFirstPersonPrimitiveType::FirstPerson;
    ViewRifle->SetCollisionProfileName(TEXT("NoCollision"));
    WorldRifle=CreateDefaultSubobject<UTempleRifleMesh>(TEXT("WorldCarbine"));
    WorldRifle->SetupAttachment(GetMesh(),Grip);
    WorldRifle->SetSkeletalMeshAsset(Weapon);
    WorldRifle->SetOwnerNoSee(true);
    WorldRifle->bCastHiddenShadow=true;
    WorldRifle->SetCollisionProfileName(TEXT("NoCollision"));
    ViewMagazine=CreateDefaultSubobject<UTempleMagazinePresentation>(TEXT("ViewMagazine"));
    ViewMagazine->SetupAttachment(ViewRifle);
    ViewMagazine->SetOnlyOwnerSee(true);
    ViewMagazine->SetCastShadow(false);
    ViewMagazine->FirstPersonPrimitiveType=EFirstPersonPrimitiveType::FirstPerson;
    WorldMagazine=CreateDefaultSubobject<UTempleMagazinePresentation>(TEXT("WorldMagazine"));
    WorldMagazine->SetupAttachment(WorldRifle);
    WorldMagazine->SetOwnerNoSee(true);
    WorldMagazine->bCastHiddenShadow=true;
    Rifle=CreateDefaultSubobject<UTempleRifleComponent>(TEXT("Carbine"));
    CreateDefaultSubobject<UTempleFootstepComponent>(TEXT("Footsteps"));
    RifleFire=Asset<UAnimSequence>(TEXT("/Game/Characters/Mannequins/Anims/Rifle/MM_Rifle_Fire.MM_Rifle_Fire"));
    RifleEquip=Asset<UAnimSequence>(TEXT("/Game/Characters/Mannequins/Anims/Rifle/MM_Rifle_Equip.MM_Rifle_Equip"));
    RifleReload=Asset<UAnimSequence>(TEXT("/Game/Characters/Mannequins/Anims/Rifle/MM_Rifle_Reload.MM_Rifle_Reload"));
    DeathClip=Asset<UAnimSequence>(TEXT("/Game/Characters/Mannequins/Anims/Death/MM_Death_Back_01.MM_Death_Back_01"));
    ShotSound=Asset<USoundBase>(TEXT("/Game/TempleTDM/Feedback/S_CanopyReport.S_CanopyReport"));
    ReloadSound=Asset<USoundBase>(TEXT("/Game/TempleTDM/Feedback/S_CarbineCycle.S_CarbineCycle"));
    ConfirmSound=Asset<USoundBase>(TEXT("/Game/TempleTDM/Feedback/S_TagConfirm.S_TagConfirm"));
    MuzzleFlash=CreateDefaultSubobject<UTempleMuzzleLight>(TEXT("CarbineFlash"));
    MuzzleFlash->SetupAttachment(WorldRifle,Muzzle);
    MuzzleFlash->SetLightColor(FLinearColor(1.f,.50f,.15f));
    MuzzleFlash->SetIntensity(8000.f);
    MuzzleFlash->SetAttenuationRadius(175.f);
    MuzzleFlash->SetCastShadows(false);
    MuzzleFlash->SetVisibility(false);
    MuzzleBurst=CreateDefaultSubobject<UNiagaraComponent>(TEXT("CarbineMuzzleBurst"));
    MuzzleBurst->SetupAttachment(MuzzleFlash);
    MuzzleBurst->SetAutoActivate(false);
    MuzzleBurst->SetCanEverAffectNavigation(false);
    auto Effect=[this](FName Name,const TCHAR* Path)
    {
        UStaticMeshComponent* EffectMesh=CreateDefaultSubobject<UStaticMeshComponent>(Name);
        EffectMesh->SetupAttachment(GetRootComponent());
        EffectMesh->SetAbsolute(true,true,true);
        EffectMesh->SetStaticMesh(Asset<UStaticMesh>(Path));
        EffectMesh->SetCastShadow(false); EffectMesh->SetCollisionProfileName(TEXT("NoCollision"));
        EffectMesh->SetCanEverAffectNavigation(false); EffectMesh->SetVisibility(false);
        return EffectMesh;
    };
    FlashParticleAsset=FSoftObjectPath(TEXT("/Game/TempleTDM/Feedback/NS_CarbineMuzzle.NS_CarbineMuzzle"));
    ImpactParticleAsset=FSoftObjectPath(TEXT("/Game/TempleTDM/Feedback/NS_CarbineContact.NS_CarbineContact"));
    TraceMesh=Effect(TEXT("Tracer"),TEXT("/Game/TempleTDM/Feedback/SM_CarbineTrace.SM_CarbineTrace"));
    MoveAction=Asset<UInputAction>(TEXT("/Game/Input/Actions/IA_Move.IA_Move"));
    LookAction=Asset<UInputAction>(TEXT("/Game/Input/Actions/IA_Look.IA_Look"));
    MouseAction=Asset<UInputAction>(TEXT("/Game/Input/Actions/IA_MouseLook.IA_MouseLook"));
    JumpAction=Asset<UInputAction>(TEXT("/Game/Input/Actions/IA_Jump.IA_Jump"));
    Contexts.Add(Asset<UInputMappingContext>(TEXT("/Game/Input/IMC_Default.IMC_Default")));
    Contexts.Add(Asset<UInputMappingContext>(TEXT("/Game/Input/IMC_MouseLook.IMC_MouseLook")));
    Contexts.Add(Asset<UInputMappingContext>(TEXT("/Game/AstraTemple/Input/IMC_TempleAZERTY.IMC_TempleAZERTY")));
}

void ATempleFighter::BeginPlay()
{
    Super::BeginPlay();
    if (HasAuthority()) Health=MaxHealth;
    ViewArms->SetVisibility(false,true);
    ViewArms->SetComponentTickEnabled(false);
    if (FSlateApplication::IsInitialized())
        FSlateApplication::Get().OnApplicationActivationStateChanged().AddUObject(this,&ATempleFighter::OnApplicationActive);
    if (GetNetMode()!=NM_DedicatedServer)
    {
        MuzzleBurst->SetAsset(FlashParticleAsset.LoadSynchronous());
        ImpactParticles=ImpactParticleAsset.LoadSynchronous();
        Attenuation=NewObject<USoundAttenuation>(this);
        Attenuation->Attenuation.bAttenuate=true;
        Attenuation->Attenuation.bSpatialize=true;
        Attenuation->Attenuation.AttenuationShapeExtents=FVector(370,0,0);
        Attenuation->Attenuation.FalloffDistance=5200;
        for (USkeletalMeshComponent* BodyPart : {GetMesh(),ViewArms.Get()})
            for (int32 I=0; I<BodyPart->GetNumMaterials(); ++I)
                if (UMaterialInstanceDynamic* Mat=BodyPart->CreateAndSetMaterialInstanceDynamic(I)) TeamMaterials.Add(Mat);
        OnRep_Team();
        if (RifleEquip)
            if (UAnimInstance* Anim=GetMesh()->GetAnimInstance())
                Anim->PlaySlotAnimationAsDynamicMontage(RifleEquip,TEXT("DefaultSlot"),.025f,.11f,RifleEquip->GetPlayLength()/.52f);
    }
    AddContexts();
}

void ATempleFighter::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const
{
    Super::GetLifetimeReplicatedProps(OutLifetimeProps);
    DOREPLIFETIME(ATempleFighter,Team); DOREPLIFETIME(ATempleFighter,Health);
    DOREPLIFETIME(ATempleFighter,ProtectedUntil);
    DOREPLIFETIME(ATempleFighter,BotAppearance);
    DOREPLIFETIME(ATempleFighter,bAiming); DOREPLIFETIME(ATempleFighter,bSprinting);
}

void ATempleFighter::PossessedBy(AController* NewController)
{
    Super::PossessedBy(NewController);
    SelectBotAppearance(NewController);
    if (NewController->IsPlayerController() && !bPlayerCrowdRegistered)
        if (auto* Crowd=UCrowdManager::GetCurrent(this))
        {
            Crowd->RegisterAgent(this);
            bPlayerCrowdRegistered=true;
        }
}

void ATempleFighter::LeavePlayerCrowd()
{
    if (!bPlayerCrowdRegistered) return;
    if (auto* Crowd=UCrowdManager::GetCurrent(this)) Crowd->UnregisterAgent(this);
    bPlayerCrowdRegistered=false;
}

void ATempleFighter::UnPossessed()
{
    MuzzleFlash->StopFlash();
    LeavePlayerCrowd();
    Super::UnPossessed();
}

FVector ATempleFighter::GetCrowdAgentLocation() const { return GetNavAgentLocation(); }

void ATempleFighter::GetCrowdAgentCollisions(float& Radius,float& HalfHeight) const
{
    GetCapsuleComponent()->GetScaledCapsuleSize(Radius,HalfHeight);
}

void ATempleFighter::EndPlay(const EEndPlayReason::Type Reason)
{
    CancelBotAppearanceLoad();
    LeavePlayerCrowd();
    if (FSlateApplication::IsInitialized()) FSlateApplication::Get().OnApplicationActivationStateChanged().RemoveAll(this);
    Rifle->Cancel();
    Super::EndPlay(Reason);
}

void ATempleFighter::SetTeam(uint8 NewTeam)
{
    if (HasAuthority() && NewTeam<=1) { Team=NewTeam; OnRep_Team(); ForceNetUpdate(); }
}

void ATempleFighter::OnRep_Team()
{
    if (Team>1) return;
    const FLinearColor Paint=Team==0?FLinearColor(.80f,.055f,.028f):FLinearColor(.025f,.25f,.85f);
    if (BotArmbandPaint) BotArmbandPaint->SetVectorParameterValue(TEXT("Color"), Paint);
    for (UMaterialInstanceDynamic* Mat : TeamMaterials)
    {
        Mat->SetVectorParameterValue(TEXT("Paint Tint"),Paint);
        Mat->SetVectorParameterValue(TEXT("LogoTint"),Paint*1.35f);
    }
}

float ATempleFighter::ServerClock() const
{
    const AGameStateBase* State=GetWorld()->GetGameState();
    return State?State->GetServerWorldTimeSeconds():GetWorld()->GetTimeSeconds();
}
bool ATempleFighter::CombatActive() const
{
    if (const auto* Mode=GetWorld()->GetAuthGameMode<ATempleMatchMode>()) return Mode->IsCombatActive();
    const auto* Match=GetWorld()->GetGameState<ATempleGameState>();
    return Match && Match->Phase==2;
}
int32 ATempleFighter::GetMagazineAmmo() const { return Rifle->GetAmmo(); }
int32 ATempleFighter::GetReserveAmmo() const { return Rifle->GetReserve(); }
int32 ATempleFighter::GetMagazineCapacity() const { return Rifle->GetCapacity(); }
bool ATempleFighter::IsReloading() const { return Rifle->IsReloading(); }
float ATempleFighter::GetReloadAlpha() const { return Rifle->ReloadAlpha(); }
bool ATempleFighter::IsSpawnProtected() const { return ProtectedUntil>ServerClock(); }
void ATempleFighter::GrantSpawnProtection(float Seconds)
{
    if (HasAuthority()) { ProtectedUntil=ServerClock()+FMath::Max(0.f,Seconds); ForceNetUpdate(); }
}

void ATempleFighter::PawnClientRestart() { Super::PawnClientRestart(); AddContexts(); }
void ATempleFighter::AddContexts()
{
    APlayerController* PC=Cast<APlayerController>(GetController());
    if (!PC || !PC->IsLocalController() || !PC->GetLocalPlayer()) return;
    if (auto* Input=ULocalPlayer::GetSubsystem<UEnhancedInputLocalPlayerSubsystem>(PC->GetLocalPlayer()))
        for (int32 I=0; I<Contexts.Num(); ++I)
            if (Contexts[I] && !Input->HasMappingContext(Contexts[I])) Input->AddMappingContext(Contexts[I],I==2?1:0);
}
void ATempleFighter::SetupPlayerInputComponent(UInputComponent* Input)
{
    Super::SetupPlayerInputComponent(Input);
    if (UEnhancedInputComponent* Enhanced=Cast<UEnhancedInputComponent>(Input))
    {
        Enhanced->BindAction(MoveAction,ETriggerEvent::Triggered,this,&ATempleFighter::Move);
        Enhanced->BindAction(MouseAction,ETriggerEvent::Triggered,this,&ATempleFighter::MouseLook);
        Enhanced->BindAction(LookAction,ETriggerEvent::Triggered,this,&ATempleFighter::PadLook);
        Enhanced->BindAction(JumpAction,ETriggerEvent::Started,this,&ATempleFighter::JumpInput);
        Enhanced->BindAction(JumpAction,ETriggerEvent::Completed,this,&ACharacter::StopJumping);
    }
    Input->BindKey(EKeys::LeftMouseButton,IE_Pressed,this,&ATempleFighter::StartFireInput);
    Input->BindKey(EKeys::LeftMouseButton,IE_Released,this,&ATempleFighter::StopFireInput);
    Input->BindKey(EKeys::RightMouseButton,IE_Pressed,this,&ATempleFighter::StartADS);
    Input->BindKey(EKeys::RightMouseButton,IE_Released,this,&ATempleFighter::StopADS);
    Input->BindKey(EKeys::R,IE_Pressed,this,&ATempleFighter::ReloadInput);
    Input->BindKey(EKeys::LeftShift,IE_Pressed,this,&ATempleFighter::SprintOn);
    Input->BindKey(EKeys::LeftShift,IE_Released,this,&ATempleFighter::SprintOff);
    Input->BindKey(EKeys::LeftControl,IE_Pressed,this,&ATempleFighter::CrouchOn);
    Input->BindKey(EKeys::LeftControl,IE_Released,this,&ATempleFighter::CrouchOff);
    AddContexts();
}
void ATempleFighter::Move(const FInputActionValue& V)
{
    if (!MayUseInput()) return;
    const FVector2D Axis=V.Get<FVector2D>();
    AddMovementInput(GetActorForwardVector(),Axis.Y); AddMovementInput(GetActorRightVector(),Axis.X);
}
void ATempleFighter::MouseLook(const FInputActionValue& V)
{
    if (!MayUseInput(true)) return;
    const FVector2D Axis=V.Get<FVector2D>()*FMath::Lerp(1.f,.70f,AimAlpha);
    AddControllerYawInput(Axis.X); AddControllerPitchInput(Axis.Y);
}
void ATempleFighter::PadLook(const FInputActionValue& V)
{
    const FVector2D Axis=V.Get<FVector2D>()*GetWorld()->GetDeltaSeconds()*115.f;
    if (MayUseInput(true)) { AddControllerYawInput(Axis.X); AddControllerPitchInput(Axis.Y); }
}
bool ATempleFighter::MayUseInput(bool bAllowCountdown) const
{
    const auto* PC=Cast<ATemplePlayerController>(GetController());
    const auto* State=GetWorld()->GetGameState<ATempleGameState>();
    return IsAlive() && PC && !PC->bScoreboardVisible && !PC->bShowMouseCursor && State &&
        (State->Phase==2 || (bAllowCountdown && State->Phase==1));
}
void ATempleFighter::OnApplicationActive(bool bActive)
{
    if (!bActive && IsPlayerControlled() && IsLocallyControlled())
    { StopFireInput(); StopADS(); SprintOff(); StopJumping(); CrouchOff(); }
}
void ATempleFighter::JumpInput() { if (MayUseInput()) Jump(); }
void ATempleFighter::ReloadInput() { if (MayUseInput()) StartReload(); }
void ATempleFighter::StartFireInput() { if (MayUseInput()) SetTriggerHeld(true); }
void ATempleFighter::StopFireInput() { SetTriggerHeld(false); }
void ATempleFighter::StartADS() { if (MayUseInput()) SetAiming(true); }
void ATempleFighter::StopADS() { SetAiming(false); }
void ATempleFighter::SprintOn() { if (MayUseInput()) SetSprinting(true); }
void ATempleFighter::SprintOff() { SetSprinting(false); }
void ATempleFighter::CrouchOn() { if (MayUseInput()) { SetSprinting(false); Crouch(); } }
void ATempleFighter::CrouchOff() { UnCrouch(); }

void ATempleFighter::SetTriggerHeld(bool Pressed)
{
    if (Pressed && !IsAlive()) return;
    if (Pressed) SetSprinting(false);
    if (!HasAuthority())
    {
        if (!IsLocallyControlled() || !IsPlayerControlled() || Rifle->IsLocalTriggerHeld()==Pressed) return;
        const int32 PullId=Rifle->SetLocalHeld(Pressed);
        ServerSetTrigger(Pressed,PullId,GetControlRotation().Vector());
        return;
    }
    Rifle->SetHeld(Pressed);
}
void ATempleFighter::ServerSetTrigger_Implementation(bool Pressed,int32 PullId,FVector_NetQuantizeNormal ViewDirection)
{
    if (Pressed && !IsAlive()) return;
    if (Pressed)
    {
        if(!Controller || !IsPlayerControlled() || ViewDirection.ContainsNaN() || !ViewDirection.IsNormalized())return;
        // Movement packets and trigger presses arrive separately. Aim from the view that produced this press.
        const FRotator View=ViewDirection.Rotation();
        Controller->SetControlRotation(View);
        FaceRotation(View,0.f);
        SetSprinting(false);
    }
    Rifle->SetHeld(Pressed,PullId);
    if (!Pressed && PullId) ClientTriggerClosed(PullId,Rifle->GetAmmo());
}
void ATempleFighter::ClientTriggerClosed_Implementation(int32 PullId,int32 AuthoritativeAmmo)
{
    Rifle->CloseLocalPull(PullId,AuthoritativeAmmo);
}
void ATempleFighter::SetAiming(bool Pressed)
{
    if (Pressed && !IsAlive()) return;
    bAiming=Pressed;
    if (Pressed) bSprinting=false;
    RefreshPace();
    if (!HasAuthority()) ServerSetAiming(Pressed);
}
void ATempleFighter::ServerSetAiming_Implementation(bool Pressed) { SetAiming(Pressed); }
void ATempleFighter::SetSprinting(bool Pressed)
{
    if (Pressed && (!IsAlive() || IsReloading() || bIsCrouched)) return;
    bSprinting=Pressed;
    if (Pressed) { bAiming=false; if (HasAuthority()) Rifle->SetHeld(false); }
    RefreshPace();
    if (!HasAuthority()) ServerSetSprinting(Pressed);
}
void ATempleFighter::ServerSetSprinting_Implementation(bool Pressed) { SetSprinting(Pressed); }
void ATempleFighter::RefreshPace() { GetCharacterMovement()->MaxWalkSpeed=bAiming?325.f:(bSprinting?690.f:510.f); }
void ATempleFighter::OnRep_Pace() { RefreshPace(); }
void ATempleFighter::StartReload()
{
    if (!IsAlive()) return;
    if (!HasAuthority())
    {
        if (Rifle->RequestLocalReload()) ServerStartReload();
        return;
    }
    if (GetMagazineAmmo()<GetMagazineCapacity() && GetReserveAmmo()>0)
    { SetSprinting(false); Rifle->BeginReload(); }
}
void ATempleFighter::ServerStartReload_Implementation()
{
    StartReload();
    if (!IsReloading()) ClientReloadDeclined();
}
void ATempleFighter::ClientReloadDeclined_Implementation() { Rifle->RejectLocalReload(); }

void ATempleFighter::GetActorEyesViewPoint(FVector& Out,FRotator& Rot) const
{

    Out=GetPawnViewLocation();
    Rot=Controller ? Controller->GetControlRotation() : GetActorRotation();
}

FVector ATempleFighter::WorldMuzzle() const
{
    if (BotPresentationBody)
    {
        // Cover checks use the same gameplay rig on listen and dedicated servers.
        const FTransform GameplayRifle = AuthoredWorldRifleOffset * GetMesh()->GetSocketTransform(Grip);
        return GameplayRifle.TransformPosition(WorldRifle->GetSocketTransform(Muzzle, RTS_Component).GetTranslation());
    }
    return WorldRifle->GetSocketLocation(Muzzle);
}
void ATempleFighter::FiredOnServer()
{
    ProtectedUntil=0.f;
    LastServerShotTime=GetWorld()->GetTimeSeconds();
}

float ATempleFighter::TakeDamage(float Amount,const FDamageEvent& Event,AController* Source,AActor* Causer)
{
    if (!HasAuthority() || !IsAlive() || IsSpawnProtected() || !CombatActive() || Amount<=0.f) return 0.f;
    const ATempleFighter* Other=Source?Cast<ATempleFighter>(Source->GetPawn()):nullptr;
    ATempleMatchMode* Mode=GetWorld()->GetAuthGameMode<ATempleMatchMode>();
    if (Other && (Other==this || (Other->GetTeam()==Team && !Mode->bFriendlyFire))) return 0.f;
    float Applied=FMath::Min(Health,Super::TakeDamage(Amount,Event,Source,Causer));
    if (Applied<=0.f) return 0.f;
#if !UE_BUILD_SHIPPING
    extern void RecordTempleBalanceImpact(const ATempleFighter*,const FDamageEvent&,bool);
    RecordTempleBalanceImpact(Other,Event,Applied>=Health);
#endif
    const FVector Direction=Other?(Other->GetActorLocation()-GetActorLocation()).GetSafeNormal():FVector::ZeroVector;
    LastDamageTime=GetWorld()->GetTimeSeconds(); LastDamageDirection=Direction;
    ClientDamageFeedback(Direction);
    if (Applied>=Health) Eliminate(Source);
    else Health-=Applied;
    ForceNetUpdate();
    return Applied;
}
void ATempleFighter::Eliminate(AController* Killer)
{
    if (!HasAuthority() || !IsAlive()) return;
    Health=0.f;
    bAiming=false; bSprinting=false;
    Rifle->Cancel();
    ShowDeath(); ForceNetUpdate();
    if (ATempleMatchMode* Mode=GetWorld()->GetAuthGameMode<ATempleMatchMode>()) Mode->HandleElimination(this,Killer);
}
void ATempleFighter::OnRep_Health() { if (!IsAlive()) ShowDeath(); }
void ATempleFighter::ShowDeath()
{
    LeavePlayerCrowd();
    if (bShowingDeath) return;
    bShowingDeath=true;
    MuzzleFlash->StopFlash();
    GetCharacterMovement()->StopMovementImmediately(); GetCharacterMovement()->DisableMovement();
    GetCapsuleComponent()->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    ViewArms->SetVisibility(false,true);
    WorldRifle->SetVisibility(false,true);
    if (DeathClip) GetMesh()->PlayAnimation(DeathClip,false);
}
void ATempleFighter::ClientDamageFeedback_Implementation(FVector_NetQuantizeNormal Direction)
{
    LastDamageTime=GetWorld()->GetTimeSeconds(); LastDamageDirection=Direction;
}
void ATempleFighter::ClientConfirmHit_Implementation(bool bKilled)
{
    if (!IsPlayerControlled() || !IsLocallyControlled()) return;
    LocalHitTime=GetWorld()->GetTimeSeconds(); bLastHitKilled=bKilled;
    if (ConfirmSound) UGameplayStatics::PlaySound2D(this,ConfirmSound,bKilled?.34f:.24f,bKilled?1.27f:1.f);
}

void ATempleFighter::PlayViewAnimation(UAnimSequence* Sequence,float Duration,float Progress)
{
    if (!Sequence || !bCalibratedView || !IsPlayerControlled() || !IsLocallyControlled()) return;
    if (UAnimInstance* Anim=ViewArms->GetAnimInstance())
        Anim->PlaySlotAnimationAsDynamicMontage(Sequence,TEXT("DefaultSlot"),.018f,.07f,
            Sequence->GetPlayLength()/FMath::Max(.05f,Duration),1,-1.f,Sequence->GetPlayLength()*Progress);
}
void ATempleFighter::MulticastReload_Implementation()
{
    if (GetNetMode()==NM_DedicatedServer) return;
    ViewMagazine->PlayReload(Rifle->GetReloadDuration());
    WorldMagazine->PlayReload(Rifle->GetReloadDuration());
    PlayViewAnimation(RifleReload,Rifle->GetReloadDuration());
    if (RifleReload)
        if (UAnimInstance* Anim=GetMesh()->GetAnimInstance())
            Anim->PlaySlotAnimationAsDynamicMontage(RifleReload,TEXT("DefaultSlot"),.09f,.13f,
                RifleReload->GetPlayLength()/Rifle->GetReloadDuration());
    if (ReloadSound)
        UGameplayStatics::PlaySoundAtLocation(this,ReloadSound,GetActorLocation(),.33f,1.f,0.f,Attenuation);
}
FVector ATempleFighter::PresentationMuzzle() const
{
    if (!bCalibratedView || !IsPlayerControlled() || !IsLocallyControlled()) return WorldRifle->GetSocketLocation(Muzzle);
    FMinimalViewInfo View;
    FirstPersonCamera->GetCameraView(0,View);
    return View.TransformWorldToFirstPerson(ViewRifle->GetSocketLocation(Muzzle),false);
}
void ATempleFighter::PlayShotPresentation(const FRotator& Heading)
{
    const bool First=IsPlayerControlled() && IsLocallyControlled();
    LocalShotTime=GetWorld()->GetTimeSeconds();
    Kick=1.f;
    if (First)
    {
        PlayViewAnimation(RifleFire,.14f);
        RecoilPitch=FMath::Min(RecoilPitch+(bAiming?.36f:.60f),2.7f);
        RecoilYaw=FMath::Clamp(RecoilYaw+FMath::FRandRange(-.20f,.20f),-.9f,.9f);
    }
    if (RifleFire)
        if (UAnimInstance* Anim=GetMesh()->GetAnimInstance())
            Anim->PlaySlotAnimationAsDynamicMontage(RifleFire,TEXT("DefaultSlot"),.015f,.04f,RifleFire->GetPlayLength()/.16f);
    const FVector Origin=PresentationMuzzle();
    if (!First || (bCalibratedView && ViewRifle->IsVisible()))
        MuzzleFlash->StartFlash(First ? ViewRifle.Get() : WorldRifle.Get(), First ? FirstPersonCamera.Get() : nullptr, MuzzleBurst, Heading);
    if (ShotSound) UGameplayStatics::PlaySoundAtLocation(this,ShotSound,Origin,First?.58f:.66f,FMath::FRandRange(.96f,1.07f),0.f,Attenuation);
}
void ATempleFighter::MulticastShot_Implementation(FVector_NetQuantize End,FVector_NetQuantizeNormal Normal,bool bImpact,bool bFighterImpact,int32 PullId,int32 ShotIndex)
{
    if (GetNetMode()==NM_DedicatedServer) return;
    const FVector Origin=PresentationMuzzle();
    const FVector Travel=FVector(End)-Origin;
    const FRotator Heading=Travel.Rotation();
    if (HasAuthority() || !IsLocallyControlled() || Rifle->NeedsOwnerPresentation(PullId,ShotIndex))
        PlayShotPresentation(Heading);
    const float Length=Travel.Size();
    const float TrailLength=FMath::Min(Length*.68f,600.f);
    TraceMesh->SetWorldLocationAndRotation(Origin+Travel.GetSafeNormal()*FMath::Min(Length*.16f,120.f),Heading);
    TraceMesh->SetWorldScale3D(FVector(TrailLength/100.f,1,1));
    TraceMesh->SetVisibility(Length>90.f); TraceUntil=GetWorld()->GetTimeSeconds()+.045f;
    if (bImpact && ImpactParticles)
    {
        UNiagaraFunctionLibrary::SpawnSystemAtLocation(this,ImpactParticles,FVector(End)+FVector(Normal)*1.5f,
            FVector(Normal).Rotation(),FVector(bFighterImpact?.72f:1.f),true,true,ENCPoolMethod::AutoRelease);
    }
}

bool ATempleFighter::IsFirstPersonViewSettled() const
{
    return bViewWasActive && bCalibratedView && GetWorld()->GetTimeSeconds()>=ViewEquipEndsAt;
}

void ATempleFighter::RefreshView(float Dt)
{
    const bool First=IsPlayerControlled() && IsLocallyControlled() && IsAlive();
    const float Now=GetWorld()->GetTimeSeconds();
    if (First!=bViewWasActive)
    {
        bViewWasActive=First;
        bCalibratedView=false;
        ViewPoseStartedAt=Now;
        ViewArms->SetVisibility(false,true);
        ViewArms->SetRelativeLocationAndRotation(ViewRest,FRotator(0,-90,0));
        ViewArms->SetComponentTickEnabled(First);
    }
    if (!First) return;
    const FTransform Frame=FirstPersonCamera->GetComponentTransform();
    const bool bWasCalibrated=bCalibratedView;
    if (!bCalibratedView && Now-ViewPoseStartedAt>.25f && ViewArms->GetAnimInstance())
    {
        ViewIdleMuzzle=Frame.InverseTransformPosition(ViewRifle->GetSocketLocation(Muzzle));
        // The imported rifle's bore is +Y, and the original authored grip includes wrist cant.
        const FTransform Gun=ViewRifle->GetComponentTransform().GetRelativeTransform(Frame);
        const FQuat Bore=FRotationMatrix::MakeFromXZ(Gun.GetUnitAxis(EAxis::Y),Gun.GetUnitAxis(EAxis::Z)).ToQuat();
        SightCorrection=Bore.Inverse();
        HipCorrection=FRotationMatrix::MakeFromXZ(FVector(1,-.085f,.048f),FVector::UpVector).ToQuat()*SightCorrection;
        bCalibratedView=true;
        const float EquipDuration=RifleEquip && !IsReloading() && Now-LocalShotTime>.2f ? ViewEquipSeconds : 0.f;
        ViewEquipEndsAt=Now+EquipDuration;
        if (EquipDuration>0.f) PlayViewAnimation(RifleEquip,EquipDuration);
        else if (IsReloading()) PlayViewAnimation(RifleReload,Rifle->GetReloadDuration(),GetReloadAlpha());
        else if (Now-LocalShotTime<.14f) PlayViewAnimation(RifleFire,.14f,(Now-LocalShotTime)/.14f);
    }
    AimAlpha=FMath::FInterpTo(AimAlpha,bAiming&&!IsReloading()?1.f:0.f,Dt,14.f);
    FirstPersonCamera->SetFieldOfView(FMath::Lerp(HipFov,AimFov,AimAlpha));
    FirstPersonCamera->FirstPersonFieldOfView=FMath::Lerp(104.f,83.f,AimAlpha);
    FirstPersonCamera->SetRelativeLocation(FVector(0,0,BaseEyeHeight));
    if (bCalibratedView)
    {
        // The front post on SKM_Rifle is 6.8 cm above the muzzle socket.
        const float ReloadProgress=GetReloadAlpha();
        const float ReloadPose=FMath::Clamp(FMath::Min(ReloadProgress,1.f-ReloadProgress)*9.f,0.f,1.f);
        const FVector Anchor=FMath::Lerp(FVector(68,17,-12.8f),FVector(72,0,-6.8f),AimAlpha)+FVector(-3,-11,2)*ReloadPose;
        // Align the two iron sights even as the base pose breathes; retain the authored kick during shots.
        const FQuat RestRotation=FRotator(0,-90,0).Quaternion();
        const FTransform ArmFrame=ViewArms->GetComponentTransform();
        const FQuat GunRotation=RestRotation*ViewRifle->GetComponentTransform().GetRelativeTransform(ArmFrame).GetRotation();
        const FQuat LiveSight=FRotationMatrix::MakeFromXZ(GunRotation.GetAxisY(),GunRotation.GetAxisZ()).ToQuat().Inverse();
        const float Settle=FMath::Clamp((Now-LocalShotTime-.13f)/.12f,0.f,1.f);
        const FQuat AimCorrection=FQuat::Slerp(SightCorrection,LiveSight,Settle);
        const FQuat Correction=FQuat::Slerp(HipCorrection,AimCorrection,AimAlpha).GetNormalized();
        const FVector LiveMuzzle=RestRotation.RotateVector(ArmFrame.InverseTransformPosition(ViewRifle->GetSocketLocation(Muzzle)));
        const FVector MuzzleOffset=FMath::Lerp(ViewIdleMuzzle-ViewRest,LiveMuzzle,AimAlpha*Settle);
        const float Speed=GetVelocity().Size2D()/510.f;
        const float Sway=FMath::Sin(Now*(bSprinting?13.f:10.f))*FMath::Min(1.f,Speed)*(1-AimAlpha);
        const FVector RearwardKick(-Kick*2.3f,Sway*.52f,-FMath::Abs(Sway)*.8f-(bSprinting?3.f:0.f));
        if (IsReloading() || Now-LocalShotTime<.14f) ViewEquipEndsAt=FMath::Min(ViewEquipEndsAt,Now);
        // Lift the world-authored equip clip into frame after the forearm clears the camera.
        const float DrawProgress=1.f-FMath::Clamp((ViewEquipEndsAt-Now)/ViewEquipSeconds,0.f,1.f);
        const FVector DrawOffset=FVector(14.f,0.f,-62.f)*(1.f-FMath::SmoothStep(.54f,.99f,DrawProgress));
        ViewArms->SetRelativeLocationAndRotation(Anchor-Correction.RotateVector(MuzzleOffset)+RearwardKick+DrawOffset,Correction*RestRotation);
        if (!bWasCalibrated) ViewArms->SetVisibility(true,true);
    }
#if !UE_BUILD_SHIPPING
    if (Now>NextViewReport && FParse::Param(FCommandLine::Get(),TEXT("TempleViewDiagnostics")))
    {
        NextViewReport=Now+1.f;
        auto* PC=Cast<APlayerController>(GetController());
        const FVector MuzzleWorld=ViewRifle->GetSocketLocation(Muzzle);
        UE_LOG(LogTemp,Display,TEXT("TempleView p=%s owner=%s target=%s eye=%s armVis=%d gunVis=%d armPose=%s bodyPose=%s cal=%s anchor=%s muzzle=%s grip=%s center=%s bounds=%s"),
            *GetName(),*GetNameSafe(GetOwner()),*GetNameSafe(PC?PC->GetViewTarget():nullptr),
            *Frame.GetLocation().ToCompactString(),ViewArms->IsVisible(),ViewRifle->IsVisible(),*GetNameSafe(ViewArms->GetAnimInstance()),
            *GetNameSafe(GetMesh()->GetAnimInstance()),*ViewIdleMuzzle.ToCompactString(),
            *ViewArms->GetRelativeLocation().ToCompactString(),*Frame.InverseTransformPosition(MuzzleWorld).ToCompactString(),
            *Frame.InverseTransformPosition(ViewArms->GetSocketLocation(Grip)).ToCompactString(),
            *Frame.InverseTransformPosition(ViewRifle->Bounds.Origin).ToCompactString(),*ViewRifle->Bounds.BoxExtent.ToCompactString());
    }
#endif
    const float NextPitch=FMath::FInterpTo(RecoilPitch,0.f,Dt,19.f);
    const float NextYaw=FMath::FInterpTo(RecoilYaw,0.f,Dt,19.f);
    if (AController* PC=GetController())
    {
        FRotator Rot=PC->GetControlRotation(); Rot.Pitch+=RecoilPitch-NextPitch; Rot.Yaw+=RecoilYaw-NextYaw;
        PC->SetControlRotation(Rot);
    }
    RecoilPitch=NextPitch; RecoilYaw=NextYaw; Kick=FMath::FInterpTo(Kick,0.f,Dt,20.f);
}
void ATempleFighter::Tick(float Dt)
{
    Super::Tick(Dt);
    if (GetNetMode()==NM_DedicatedServer) return;
    RefreshView(Dt);
    const float Now=GetWorld()->GetTimeSeconds();
    if (TraceMesh->IsVisible()&&Now>=TraceUntil) TraceMesh->SetVisibility(false);
#if !UE_BUILD_SHIPPING
    UpdateTempleBodyReview(this);
#endif
}
