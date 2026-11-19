#include "TempleMatch.h"
#if PLATFORM_WASM
#include <emscripten/em_asm.h>
#endif
#include "TempleDeploymentNavigation.h"
#include "TempleFighter.h"
#include "TempleBotController.h"
#include "TempleHUD.h"
#include "Blueprint/UserWidget.h"
#include "Camera/PlayerCameraManager.h"
#include "Components/CapsuleComponent.h"
#include "Engine/World.h"
#include "Engine/TargetPoint.h"
#include "Components/InputComponent.h"
#include "EngineUtils.h"
#include "GameFramework/GameSession.h"
#include "GameFramework/PlayerStart.h"
#include "Kismet/GameplayStatics.h"
#include "Kismet/KismetSystemLibrary.h"
#include "Misc/CommandLine.h"
#include "NavigationSystem.h"
#include "Net/UnrealNetwork.h"
#include "InputCoreTypes.h"

#if !UE_BUILD_SHIPPING
void RecordTempleBalanceSpawn(const ATemplePlayerState* Player,const APlayerStart* Start,float Ally,float Enemy,int32 Visible,bool bRespawn);
void RecordTempleBaseReturn(const ATemplePlayerState* Player,const FVector& Location);
#endif

void ATemplePlayerState::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const
{
    Super::GetLifetimeReplicatedProps(OutLifetimeProps);
    DOREPLIFETIME(ATemplePlayerState,Team);
    DOREPLIFETIME(ATemplePlayerState,Kills);
    DOREPLIFETIME(ATemplePlayerState,Deaths);
    DOREPLIFETIME(ATemplePlayerState,RespawnAt);
}

void ATempleGameState::StartPhase(int32 NewPhase, float Duration)
{
    Phase = NewPhase;
    PhaseDuration = Duration;
    PhaseEndsAt = GetWorld()->GetTimeSeconds() + Duration;
    ForceNetUpdate();
}

int32 ATempleGameState::RemainingPhaseSeconds(double ServerNow) const
{
    const double Remaining = FMath::Clamp(PhaseEndsAt - ServerNow, 0.0, static_cast<double>(PhaseDuration));
    return FMath::CeilToInt32(Remaining);
}

void ATempleGameState::GetLifetimeReplicatedProps(TArray<FLifetimeProperty>& OutLifetimeProps) const
{
    Super::GetLifetimeReplicatedProps(OutLifetimeProps);
    DOREPLIFETIME(ATempleGameState,RedScore);
    DOREPLIFETIME(ATempleGameState,BlueScore);
    DOREPLIFETIME(ATempleGameState,ScoreLimit);
    DOREPLIFETIME(ATempleGameState,RespawnDelay);
    DOREPLIFETIME(ATempleGameState,Phase);
    DOREPLIFETIME(ATempleGameState,PhaseEndsAt);
    DOREPLIFETIME(ATempleGameState,PhaseDuration);
    DOREPLIFETIME(ATempleGameState,WinnerTeam);
    DOREPLIFETIME(ATempleGameState,Feed);
    DOREPLIFETIME(ATempleGameState,FinalStandings);
}

void ATemplePlayerController::ClientSetRotation_Implementation(FRotator NewRotation,bool bResetCamera)
{
    Super::ClientSetRotation_Implementation(NewRotation,bResetCamera);
    if(bResetCamera && IsLocalPlayerController() && GetPawn() && GetViewTarget()==GetPawn() && PlayerCameraManager)
    {
        // Respawn and team changes can arrive after this frame's regular camera update.
        PlayerCameraManager->SetGameCameraCutThisFrame();
        PlayerCameraManager->UpdateCamera(0.f);
    }
}

void ATemplePlayerController::BeginPlay()
{
    Super::BeginPlay();
    if (IsLocalController() && GetNetMode()!=NM_DedicatedServer)
    {
        Overlay=CreateWidget<UTempleCombatHUD>(this,UTempleCombatHUD::StaticClass());
        if (Overlay) Overlay->AddToPlayerScreen(10);
        SetInputMode(FInputModeGameOnly());
    }
}
void ATemplePlayerController::SetupInputComponent()
{
    Super::SetupInputComponent();
    InputComponent->BindKey(EKeys::Tab,IE_Pressed,this,&ATemplePlayerController::OpenScoreboard);
    InputComponent->BindKey(EKeys::Enter,IE_Pressed,this,&ATemplePlayerController::ReplayMatch);
    InputComponent->BindKey(EKeys::One,IE_Pressed,this,&ATemplePlayerController::SelectRed);
    InputComponent->BindKey(EKeys::Two,IE_Pressed,this,&ATemplePlayerController::SelectBlue);
    InputComponent->BindKey(EKeys::Escape,IE_Pressed,this,&ATemplePlayerController::ToggleMenu).bExecuteWhenPaused=true;
}
void ATemplePlayerController::PlayerTick(float DeltaTime)
{
    Super::PlayerTick(DeltaTime);
    if (IsLocalController()) RefreshInteraction();
}
void ATemplePlayerController::RefreshInteraction()
{
    const ATempleGameState* State=GetWorld()->GetGameState<ATempleGameState>();
    const auto* PS=GetPlayerState<ATemplePlayerState>();
    const bool bInteractive=bMenuOpen || bScoreboardVisible || (State && State->Phase==3) || (PS && PS->Team==255);
    if (bInteractive==bHasInteractiveHUD) return;
    bHasInteractiveHUD=bInteractive;
    bShowMouseCursor=bInteractive;
    if (bInteractive)
    {
        if (auto* F=Cast<ATempleFighter>(GetPawn())) {F->SetTriggerHeld(false); F->SetAiming(false);}
        FInputModeGameAndUI Mode;
        Mode.SetHideCursorDuringCapture(false);
        if(Overlay) Mode.SetWidgetToFocus(Overlay->TakeWidget());
        SetInputMode(Mode);
    }
    else SetInputMode(FInputModeGameOnly());
}
void ATemplePlayerController::OpenScoreboard(){ if(!bMenuOpen)SetScoreboardVisible(true); }
void ATemplePlayerController::SetScoreboardVisible(bool bVisible){bScoreboardVisible=bVisible; RefreshInteraction();}
void ATemplePlayerController::SetMenuOpen(bool bOpen)
{
    if(!IsLocalController() || bMenuOpen==bOpen)return;
    bMenuOpen=bOpen;
    if(bOpen)bScoreboardVisible=false;
    if(GetNetMode()==NM_Standalone)SetPause(bOpen);
    RefreshInteraction();
}
void ATemplePlayerController::ToggleMenu()
{
    if(bScoreboardVisible){SetScoreboardVisible(false);return;}
    SetMenuOpen(!bMenuOpen);
}
void ATemplePlayerController::OpenTeamsFromMenu()
{
    SetMenuOpen(false);SetScoreboardVisible(true);
}
void ATemplePlayerController::QuitGame()
{
    if (!IsLocalController()) return;
#if PLATFORM_WASM
    MAIN_THREAD_ASYNC_EM_ASM({ window.location.reload(); });
#else
    UKismetSystemLibrary::QuitGame(this,this,EQuitPreference::Quit,false);
#endif
}
void ATemplePlayerController::SelectRed(){if(bHasInteractiveHUD) JoinTeam(0);}
void ATemplePlayerController::SelectBlue(){if(bHasInteractiveHUD) JoinTeam(1);}
void ATemplePlayerController::JoinTeam(int32 Team){if(Team==0 || Team==1) ServerJoinTeam(Team);}
void ATemplePlayerController::ReplayMatch(){ServerReplayMatch();}
void ATemplePlayerController::ServerJoinTeam_Implementation(int32 Team)
{
    if ((Team==0 || Team==1) && GetWorld()->GetAuthGameMode<ATempleMatchMode>())
        GetWorld()->GetAuthGameMode<ATempleMatchMode>()->SwitchTeam(this,static_cast<uint8>(Team));
}
void ATemplePlayerController::ServerReplayMatch_Implementation()
{
    if(auto* Mode=GetWorld()->GetAuthGameMode<ATempleMatchMode>()) Mode->Replay();
}

ATempleMatchMode::ATempleMatchMode()
{
    PrimaryActorTick.bCanEverTick=true;
    PrimaryActorTick.TickInterval=.15f;
    DefaultPawnClass=ATempleFighter::StaticClass();
    BotControllerClass=ATempleBotController::StaticClass();
    PlayerControllerClass=ATemplePlayerController::StaticClass();
    PlayerStateClass=ATemplePlayerState::StaticClass();
    GameStateClass=ATempleGameState::StaticClass();
}
void ATempleMatchMode::InitGame(const FString& Map,const FString& Options,FString& Error)
{
    Super::InitGame(Map,Options,Error);
    // The same rules blueprint supplies the human loadout and the AI controller for each new world.
    const auto* Rules=GetClass()->GetDefaultObject<ATempleMatchMode>();
    DefaultPawnClass=Rules->DefaultPawnClass;
    BotControllerClass=Rules->BotControllerClass;
    ScoreTarget=FMath::Clamp(UGameplayStatics::GetIntOption(Options,TEXT("ScoreLimit"),ScoreTarget),1,500);
    TeamSize=FMath::Clamp(UGameplayStatics::GetIntOption(Options,TEXT("TeamSize"),TeamSize),1,12);
    FString DuelBot;
    if (GetNetMode() == NM_Standalone && FParse::Value(FCommandLine::Get(), TEXT("TempleDuelBot="), DuelBot))
    {
        DuelBotSlot = ATempleFighter::FindBotAppearanceSlot(FName(*DuelBot));
        if (DuelBotSlot != INDEX_NONE)
            TeamSize = 1;
    }
    GameSession->MaxPlayers=TeamSize*2;
    bFriendlyFire=UGameplayStatics::GetIntOption(Options,TEXT("FriendlyFire"),bFriendlyFire?1:0)!=0;
    MatchDuration=FMath::Clamp(float(UGameplayStatics::GetIntOption(Options,TEXT("TimeLimit"),int32(MatchDuration))),5.f,3600.f);
}
void ATempleMatchMode::DiscoverArena()
{
    Starts[0].Reset(); Starts[1].Reset(); PatrolNodes.Reset();
    for(auto& Lane:PatrolLanes)Lane.Reset();
    BaseCenters[0]=BaseCenters[1]=FVector::ZeroVector;
    for(TActorIterator<APlayerStart> It(GetWorld()); It; ++It)
    {
        int32 Team=It->PlayerStartTag==TEXT("Red")?0:It->PlayerStartTag==TEXT("Blue")?1:INDEX_NONE;
        if(Team==INDEX_NONE) continue;
        Starts[Team].Add(*It);
        BaseCenters[Team]+=It->GetActorLocation();
    }
    for(int32 Team=0;Team<2;++Team)
        if(Starts[Team].Num()) BaseCenters[Team]/=Starts[Team].Num();
    for(TActorIterator<ATargetPoint> It(GetWorld()); It; ++It)
    {
        if(!It->ActorHasTag(TEXT("TemplePatrol")))continue;
        const FVector Position=It->GetActorLocation();
        PatrolNodes.Add(Position);
        for(FName Tag:It->Tags)
        {
            TArray<FString> Parts;
            Tag.ToString().ParseIntoArray(Parts,TEXT("."));
            if(Parts.Num()!=3 || Parts[0]!=TEXT("Patrol") || !Parts[1].IsNumeric() || !Parts[2].IsNumeric())continue;
            const int32 Lane=FCString::Atoi(*Parts[1]), Station=FCString::Atoi(*Parts[2]);
            if(Lane<0 || Lane>=4 || Station<0 || Station>=64)continue;
            auto& Nodes=PatrolLanes[Lane];
            if(Nodes.Num()<=Station)Nodes.SetNum(Station+1);
            Nodes[Station]=Position;
        }
    }
}
void ATempleMatchMode::StartPlay()
{
    DiscoverArena();
    Super::StartPlay();
    bReady=true;
    StartRound();
}
uint8 ATempleMatchMode::SmallerTeam() const
{
    int32 Count[2]={};
    for(FConstControllerIterator It=GetWorld()->GetControllerIterator(); It; ++It)
        if(auto* C=It->Get()) if(auto* PS=C->GetPlayerState<ATemplePlayerState>(); PS && PS->Team<2 && C->IsPlayerController()) ++Count[PS->Team];
    return Count[0]<=Count[1]?0:1;
}
void ATempleMatchMode::ChangeName(AController* Controller, const FString& NewName, bool bNameChange)
{
    if (!Controller || !Controller->PlayerState) return;

    TSet<FString> Occupied;
    if (GameState)
    {
        for (APlayerState* Player : GameState->PlayerArray)
        {
            if (Player && Player != Controller->PlayerState) Occupied.Add(Player->GetPlayerName().ToLower());
        }
    }
    FString BaseName = NewName.TrimStartAndEnd().Left(20);
    if (BaseName.IsEmpty()) BaseName = TEXT("Ranger");
    FString AvailableName = BaseName;
    for (int32 Number = 2; Occupied.Contains(AvailableName.ToLower()); ++Number)
    {
        const FString Suffix = FString::Printf(TEXT(" %d"), Number);
        AvailableName = BaseName.Left(20 - Suffix.Len()) + Suffix;
    }
    Super::ChangeName(Controller, AvailableName, bNameChange);
}

void ATempleMatchMode::PostLogin(APlayerController* NewPlayer)
{
    if(auto* PS=NewPlayer->GetPlayerState<ATemplePlayerState>())
    {
        PS->Team=SmallerTeam();
    }
    Super::PostLogin(NewPlayer);
    if(bReady) EnsureRosters();
}
void ATempleMatchMode::Logout(AController* Exiting)
{
    LastTeamChange.Remove(Exiting);
    Super::Logout(Exiting);
}
void ATempleMatchMode::RemovePawn(AController* Controller)
{
    if(APawn* Pawn=Controller->GetPawn())
    {
        Controller->UnPossess();
        Pawn->Destroy();
    }
}
void ATempleMatchMode::RetireBot(AController* Controller)
{
    RemovePawn(Controller);
    Controller->Destroy();
}
void ATempleMatchMode::EnsureRosters()
{
    if(!bReady) return;
    TArray<ATempleBotController*> Bots[2];
    constexpr int32 AppearanceCount = ATempleBotController::AppearanceCount;
    int32 Counts[2][AppearanceCount] = {};
    int32 Humans[2]={};
    for(FConstControllerIterator It=GetWorld()->GetControllerIterator(); It; ++It)
    {
        auto* C=It->Get();
        if(!IsValid(C)) continue;
        auto* PS=C->GetPlayerState<ATemplePlayerState>();
        if(!PS || PS->Team>1) continue;
        if(C->IsPlayerController()) ++Humans[PS->Team];
        else if (ATempleBotController* Bot = Cast<ATempleBotController>(C))
        {
            Bots[PS->Team].Add(Bot);
            ++Counts[PS->Team][Bot->GetAppearanceSlot()];
        }
    }
    static const TCHAR* Names[2][12]={
        {TEXT("Cinder"),TEXT("Ocelot"),TEXT("Flint"),TEXT("Sable"),TEXT("Ibis"),TEXT("Onyx"),TEXT("Kite"),TEXT("Cedar"),TEXT("Ember"),TEXT("Aster"),TEXT("Flare"),TEXT("Mica")},
        {TEXT("Reed"),TEXT("Heron"),TEXT("Delta"),TEXT("Lynx"),TEXT("Finch"),TEXT("Silva"),TEXT("Moss"),TEXT("Indigo"),TEXT("River"),TEXT("Kestrel"),TEXT("Gale"),TEXT("Vale")}
    };
    // Remove surplus bots first. On a team switch both sides can change in one update.
    // Favor duplicates throughout the match, and then duplicates on this particular team.
    auto MoreRepresented = [&](uint8 Team, uint8 A, uint8 B)
    {
        const int32 TotalA = Counts[0][A] + Counts[1][A];
        const int32 TotalB = Counts[0][B] + Counts[1][B];
        return TotalA == TotalB ? Counts[Team][A] > Counts[Team][B] : TotalA > TotalB;
    };
    for (uint8 Team = 0; Team < 2; ++Team)
    {
        const int32 Wanted = FMath::Max(0, TeamSize - Humans[Team]);
        while (Bots[Team].Num() > Wanted)
        {
            int32 RetiredIndex = Bots[Team].Num() - 1;
            for (int32 I = 0; I < Bots[Team].Num(); ++I)
                if (MoreRepresented(Team, Bots[Team][I]->GetAppearanceSlot(), Bots[Team][RetiredIndex]->GetAppearanceSlot()))
                    RetiredIndex = I;
            ATempleBotController* Retired = Bots[Team][RetiredIndex];
            --Counts[Team][Retired->GetAppearanceSlot()];
            Bots[Team].RemoveAtSwap(RetiredIndex);
            RetireBot(Retired);
        }
    }
    for(uint8 Team=0;Team<2;++Team)
    {
        const int32 Wanted=FMath::Max(0,TeamSize-Humans[Team]);
        while(Bots[Team].Num()<Wanted)
        {
            auto* Bot=GetWorld()->SpawnActor<ATempleBotController>(BotControllerClass);
            auto* PS=Bot?Bot->GetPlayerState<ATemplePlayerState>():nullptr;
            if(!PS) {if(Bot) Bot->Destroy();break;}
            uint8 Slot = 0;
            for (uint8 I = 1; I < AppearanceCount; ++I)
                if (MoreRepresented(Team, Slot, I)) Slot = I;
            if (DuelBotSlot != INDEX_NONE)
                Slot = static_cast<uint8>(DuelBotSlot);
            Bot->SetAppearanceSlot(Slot);
            ++Counts[Team][Slot];
            PS->SetPlayerId(ATempleBotController::FirstRosterPlayerId + BotSerial++);
            TSet<FString> Used;
            for(auto* Existing:Bots[Team]) Used.Add(Existing->PlayerState->GetPlayerName());
            for(auto Name:Names[Team]) if(!Used.Contains(FString(Name))){ChangeName(Bot,Name,false);break;}
            PS->Team=Team;
            Bots[Team].Add(Bot);
            RestartPlayer(Bot);
        }
    }
}
void ATempleMatchMode::StartRound()
{
    auto* State=GetGameState<ATempleGameState>();
    if(!State) return;
    State->StartPhase(1,CountdownSeconds);
    State->ScoreLimit=ScoreTarget; State->RespawnDelay=RespawnDelay; State->RedScore=State->BlueScore=0; State->WinnerTeam=255; State->Feed.Reset();
    State->FinalStandings.Reset();
    LastTeamChange.Reset();
    TArray<AController*> Roster;
    for(FConstControllerIterator It=GetWorld()->GetControllerIterator();It;++It)
        if(auto* C=It->Get();IsValid(C) && C->GetPlayerState<ATemplePlayerState>()) Roster.Add(C);
    for(auto* C:Roster)
    {
        auto* PS=C->GetPlayerState<ATemplePlayerState>();
        PS->Kills=PS->Deaths=0; PS->RespawnAt=0;
        RemovePawn(C);RestartPlayer(C); PS->ForceNetUpdate();
    }
    EnsureRosters();
    State->ForceNetUpdate();
}
void ATempleMatchMode::Replay(){if(auto* State=GetGameState<ATempleGameState>();State && State->Phase==3) StartRound();}
bool ATempleMatchMode::IsCombatActive() const
{
    const auto* State=GetGameState<ATempleGameState>();
    return State && State->Phase==2;
}
void ATempleMatchMode::EndRound()
{
    auto* State=GetGameState<ATempleGameState>();
    if(!State || State->Phase!=2) return;
    State->StartPhase(3,0);
    State->WinnerTeam=State->RedScore==State->BlueScore?255:State->RedScore>State->BlueScore?0:1;
    State->FinalStandings.Reset(State->PlayerArray.Num());
    for(const APlayerState* Player:State->PlayerArray)
        if(const auto* Side=Cast<ATemplePlayerState>(Player); Side && Side->Team<2)State->FinalStandings.Emplace(*Side);
    State->ForceNetUpdate();
}
void ATempleMatchMode::SwitchTeam(ATemplePlayerController* Human,uint8 Team)
{
    const auto* State=GetGameState<ATempleGameState>();
    if(!Human || Team>1 || !State || State->Phase==3) return;
    auto* PS=Human->GetPlayerState<ATemplePlayerState>();
    if(!PS || PS->Team==Team) return;
    const double Now=GetWorld()->GetTimeSeconds();
    if(const double* Last=LastTeamChange.Find(Human);Last && Now-*Last<10.) return;
    int32 OnTeam=0;
    for(FConstPlayerControllerIterator It=GetWorld()->GetPlayerControllerIterator();It;++It)
        if(auto* C=It->Get()) if(auto* P=C->GetPlayerState<ATemplePlayerState>();P && P->Team==Team)++OnTeam;
    if(OnTeam>=TeamSize) return;
    LastTeamChange.Add(Human,Now); RemovePawn(Human);PS->Team=Team;
    PS->RespawnAt=IsCombatActive()?Now+RespawnDelay:0; PS->ForceNetUpdate();
    if(!IsCombatActive()) RestartPlayer(Human);
    EnsureRosters();
}
bool ATempleMatchMode::IsEnemySafeZone(uint8 Team,const FVector& Point) const
{
    if(Team>1 || Starts[1-Team].IsEmpty()) return false;
    const FVector Delta=Point-BaseCenters[1-Team];
    return FMath::Abs(Delta.Z)<TempleNavigation::SpawnHalfHeight && Delta.SizeSquared2D()<FMath::Square(TempleNavigation::SpawnRadius);
}
FVector ATempleMatchMode::GetPatrolGoal(uint8 Team,FVector From) const
{
    TArray<FVector> Candidates;
    for(const FVector& P:PatrolNodes) if(!IsEnemySafeZone(Team,P) && FVector::DistSquared2D(P,From)>FMath::Square(650.)) Candidates.Add(P);
    if(!Candidates.IsEmpty()) return Candidates[FMath::RandHelper(Candidates.Num())];
    return From;
}

bool ATempleMatchMode::GetLaneGoal(uint8 Team,int32 Lane,FVector From,int32& Station,int32& Direction,FVector& Destination) const
{
    if(Lane<0 || Lane>=4 || PatrolLanes[Lane].Num()<2)return false;
    const auto& Nodes=PatrolLanes[Lane];
    if(!Nodes.IsValidIndex(Station))
    {
        Station=0;
        for(int32 I=1;I<Nodes.Num();++I)
            if(FVector::DistSquared(From,Nodes[I])<FVector::DistSquared(From,Nodes[Station]))Station=I;
        // Terrace patrols join from their nearest approach and climb toward the sanctuary.
        Direction=(Lane==3 || Team==0)?1:-1;
        if (Nodes.IsValidIndex(Station+Direction))
        {
            // Join the lane ahead when the spawn lies partway along its next segment.
            const FVector Forward=(Nodes[Station+Direction]-Nodes[Station]).GetSafeNormal2D();
            if (FVector::DotProduct(From-Nodes[Station],Forward)>125.f) Station+=Direction;
        }
    }
    for(int32 Attempt=0;Attempt<Nodes.Num();++Attempt)
    {
        const FVector Point=Nodes[Station];
        if(FVector::DistSquared2D(From,Point)>FMath::Square(255.f) && !IsEnemySafeZone(Team,Point))
        {
            Destination=Point;
            return true;
        }
        if(!Nodes.IsValidIndex(Station+Direction))Direction*=-1;
        Station+=Direction;
    }
    return false;
}

AActor* ATempleMatchMode::ChoosePlayerStart_Implementation(AController* Player)
{
    auto* PS=Player?Player->GetPlayerState<ATemplePlayerState>():nullptr;
    if(!PS || PS->Team>1) return Super::ChoosePlayerStart_Implementation(Player);
    if(Starts[PS->Team].IsEmpty()) DiscoverArena();
    APlayerStart* Best=nullptr;
    double BestScore=-DBL_MAX;
#if !UE_BUILD_SHIPPING
    float SelectedAlly=0.f,SelectedEnemy=0.f;
    int32 SelectedSightlines=0;
#endif
    TArray<ATempleFighter*> Fighters;
    for(TActorIterator<ATempleFighter> It(GetWorld());It;++It)
        if(It->IsAlive() && It->GetController()!=Player) Fighters.Add(*It);
    for(const auto& Ref:Starts[PS->Team])
    {
        APlayerStart* Start=Ref.Get();
        if(!Start) continue;
        const FVector Point=Start->GetActorLocation();
        FCollisionQueryParams Clearance(SCENE_QUERY_STAT(TempleSpawnClearance),false,Start);
        if(Player->GetPawn()) Clearance.AddIgnoredActor(Player->GetPawn());
        if(GetWorld()->OverlapBlockingTestByChannel(Point,FQuat::Identity,ECC_Pawn,FCollisionShape::MakeCapsule(34.f,96.f),Clearance)) continue;
        double Value=FMath::FRandRange(0.f,180.f);
#if !UE_BUILD_SHIPPING
        float ClosestAlly=FLT_MAX,ClosestEnemy=FLT_MAX;
        int32 Sightlines=0;
#endif
        for(auto* Other:Fighters)
        {
            const FVector Eye=Other->GetPawnViewLocation();
            const float Distance=FVector::Dist(Point,Other->GetActorLocation());
#if !UE_BUILD_SHIPPING
            if(Other->GetTeam()==PS->Team)ClosestAlly=FMath::Min(ClosestAlly,Distance);
            else ClosestEnemy=FMath::Min(ClosestEnemy,Distance);
#endif
            if(Distance<100.f){Value-=100000;continue;}
            if(Other->GetTeam()==PS->Team){Value-=FMath::Max(0.f,250.f-Distance);continue;}
            Value-=FMath::Max(0.f,2800.f-Distance);
            if(Distance>11000 || FVector::DotProduct((Point-Eye).GetSafeNormal(),Other->GetBaseAimRotation().Vector())<.35f) continue;
            FHitResult Hit;
            FCollisionQueryParams Params(SCENE_QUERY_STAT(TempleSpawn),false,Other);
            if(!GetWorld()->LineTraceSingleByChannel(Hit,Eye,Point+FVector(0,0,45),ECC_Visibility,Params))
            {
                Value-=4500;
#if !UE_BUILD_SHIPPING
                ++Sightlines;
#endif
            }
        }
        if(Value>BestScore)
        {
            BestScore=Value;Best=Start;
#if !UE_BUILD_SHIPPING
            SelectedAlly=ClosestAlly;SelectedEnemy=ClosestEnemy;SelectedSightlines=Sightlines;
#endif
        }
    }
#if !UE_BUILD_SHIPPING
    RecordTempleBalanceSpawn(PS,Best,SelectedAlly,SelectedEnemy,SelectedSightlines,PS->RespawnAt>0);
#endif
    return Best;
}
void ATempleMatchMode::RestartPlayer(AController* Player)
{
    if(!IsValid(Player)) return;
    auto* PS=Player->GetPlayerState<ATemplePlayerState>();
    if(!PS) return;
    if(PS->Team>1) PS->Team=SmallerTeam();
    if(auto* Old=Cast<ATempleFighter>(Player->GetPawn());Old && !Old->IsAlive()) RemovePawn(Player);
    if(Player->GetPawn()) return;
    if(AActor* Start=ChoosePlayerStart(Player)) RestartPlayerAtPlayerStart(Player,Start);
    if(auto* Fighter=Cast<ATempleFighter>(Player->GetPawn()))
    {
        Fighter->SetTeam(PS->Team); Fighter->GrantSpawnProtection(SpawnProtectionSeconds);
        PS->RespawnAt=0;PS->ForceNetUpdate();
    }
    else PS->RespawnAt=GetWorld()->GetTimeSeconds()+.5f;
}
void ATempleMatchMode::HandleElimination(ATempleFighter* Victim,AController* Killer)
{
    if(!IsCombatActive() || !Victim || !Victim->GetController()) return;
    auto* State=GetGameState<ATempleGameState>();
    auto* V=Victim->GetPlayerState<ATemplePlayerState>();
    auto* K=Killer?Killer->GetPlayerState<ATemplePlayerState>():nullptr;
    if(!V || V->RespawnAt>0) return;
    ++V->Deaths;
    V->RespawnAt=GetWorld()->GetTimeSeconds()+RespawnDelay;
    if(K && K!=V && K->Team<2 && K->Team!=V->Team)
    {
        ++K->Kills;
        ++(K->Team==0?State->RedScore:State->BlueScore);
        K->ForceNetUpdate();
    }
    FTempleFeedEntry Entry;
    Entry.Killer=K?K->GetPlayerName():TEXT("Temple");
    Entry.Victim=V->GetPlayerName();
    Entry.KillerTeam=K?K->Team:255;
    Entry.VictimTeam=V->Team; Entry.Serial=++FeedSerial; Entry.ServerTime=GetWorld()->GetTimeSeconds();
    if(State->Feed.Num()>=6) State->Feed.RemoveAt(0);
    State->Feed.Add(MoveTemp(Entry));
    State->ForceNetUpdate();V->ForceNetUpdate();
    if(State->RedScore>=ScoreTarget || State->BlueScore>=ScoreTarget) EndRound();
}
void ATempleMatchMode::Tick(float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    auto* State=GetGameState<ATempleGameState>();
    if(!bReady || !State) return;
    const double Now=GetWorld()->GetTimeSeconds();
    if(State->Phase==1 && Now>=State->PhaseEndsAt)
    {
        State->StartPhase(2,MatchDuration);
    }
    if(!IsCombatActive()) return;
    if(Now>=State->PhaseEndsAt){EndRound();return;}
    if(Now>NextPopulationCheck){EnsureRosters();NextPopulationCheck=Now+3.;}
    for(FConstControllerIterator It=GetWorld()->GetControllerIterator();It;++It)
    {
        auto* C=It->Get();
        if(!IsValid(C)) continue;
        auto* PS=C->GetPlayerState<ATemplePlayerState>();
        if(!PS || PS->Team>1) continue;
        if(PS->RespawnAt>0 && Now>=PS->RespawnAt){RemovePawn(C);RestartPlayer(C);continue;}
        auto* F=Cast<ATempleFighter>(C->GetPawn());
        if(!F || !F->IsAlive()) continue;
        if(IsEnemySafeZone(PS->Team,F->GetActorLocation()) || F->GetActorLocation().Z < -650)
        {
            if(AActor* Start=ChoosePlayerStart(C))
            {
#if !UE_BUILD_SHIPPING
                RecordTempleBaseReturn(PS,F->GetActorLocation());
#endif
                F->TeleportTo(Start->GetActorLocation(),Start->GetActorRotation());
                C->SetControlRotation(Start->GetActorRotation());
            }
        }
    }
}

