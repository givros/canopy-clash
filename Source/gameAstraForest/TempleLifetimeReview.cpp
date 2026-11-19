#if !UE_BUILD_SHIPPING
#include "TempleBotController.h"
#include "TempleFighter.h"
#include "TempleHUD.h"
#include "TempleMatch.h"
#include "AudioDevice.h"
#include "AudioThread.h"
#include "Blueprint/UserWidget.h"
#include "Components/AudioComponent.h"
#include "Components/SkeletalMeshComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Components/Widget.h"
#include "Containers/Ticker.h"
#include "Engine/Engine.h"
#include "EngineUtils.h"
#include "HAL/FileManager.h"
#include "HAL/MemoryBase.h"
#include "HAL/MemoryMisc.h"
#include "HAL/PlatformMemory.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Misc/CommandLine.h"
#include "Misc/FileHelper.h"
#include "NiagaraComponent.h"
#include "NiagaraSystem.h"
#include "UObject/UObjectArray.h"
#include "UObject/UObjectIterator.h"

namespace
{
template<typename T>
int32 CountWorldInstances(UWorld* World)
{
    int32 Count = 0;
    for (TObjectIterator<T> Item; Item; ++Item)
    {
        if (Item->GetWorld() == World) ++Count;
    }
    return Count;
}

class FTempleLifetimeRecorder
{
public:
    FString Output;
    FTSTicker::FDelegateHandle TickHandle;
    FDelegateHandle PurgeHandle;
    int32 Purges = 0;

    bool Tick()
    {
        if (!GEngine) return true;
        for (const FWorldContext& Context : GEngine->GetWorldContexts())
        {
            UWorld* World = Context.World();
            if (Context.WorldType != EWorldType::Game || !World || !World->HasBegunPlay() || World->GetNetMode() != NM_Standalone) continue;
            auto* Match = World->GetGameState<ATempleGameState>();
            auto* Player = Cast<ATemplePlayerController>(World->GetFirstPlayerController());
            if (Match && Player) return SampleRound(World, Match, Player);
        }
        return true;
    }

private:
    int32 Round = 1;
    int32 RequestedPurge = 0;
    int32 MenuStep = 0;
    int32 PeakFX = 0;
    int32 PeakActiveFX = 0;
    int32 PeakActiveMuzzles = 0;
    int32 PeakDuplicateMuzzles = 0;
    int32 HighestActiveClock = 0;
    int32 RoundDuration = 0;
    double MenuOpenedAt = 0;
    double EndedAt = -1;
    double NextPeak = 0;
    bool bAwaitingPurge = false;
    bool bMenuOpened = false;
    bool bRosterOpened = false;
    TArray<TWeakObjectPtr<ATempleFighter>> PreviousPawns;
    TArray<TWeakObjectPtr<UNiagaraComponent>> PreviousMuzzles;

    struct FParticleCounts
    {
        int32 Total = 0, Active = 0, Muzzles = 0, ActiveMuzzles = 0, UniqueOwners = 0, UnownedMuzzles = 0;
        int32 DuplicateMuzzles() const { return Muzzles - UniqueOwners - UnownedMuzzles; }
    };

    FParticleCounts CountParticles(UWorld* World, TArray<TWeakObjectPtr<UNiagaraComponent>>* RememberMuzzles = nullptr) const
    {
        FParticleCounts Result;
        TSet<const ATempleFighter*> Owners;
        for (TObjectIterator<UNiagaraComponent> Item; Item; ++Item)
        {
            if (Item->GetWorld() != World) continue;
            ++Result.Total;
            if (Item->IsActive()) ++Result.Active;
            if (!Item->GetAsset() || Item->GetAsset()->GetFName() != TEXT("NS_CarbineMuzzle")) continue;
            ++Result.Muzzles;
            if (Item->IsActive()) ++Result.ActiveMuzzles;
            if (const auto* Fighter = Cast<ATempleFighter>(Item->GetOwner())) Owners.Add(Fighter);
            else ++Result.UnownedMuzzles;
            if (RememberMuzzles) RememberMuzzles->Add(*Item);
        }
        Result.UniqueOwners = Owners.Num();
        return Result;
    }

    void Record(UWorld* World, ATempleGameState* Match, const TCHAR* Stage) const
    {
        const FParticleCounts FX = CountParticles(World);
        int32 RemainingOldPawns = 0;
        for (const auto& Pawn : PreviousPawns) if (Pawn.GetEvenIfUnreachable()) ++RemainingOldPawns;
        int32 RemainingOldMuzzles = 0;
        for (const auto& PreviousMuzzle : PreviousMuzzles) if (PreviousMuzzle.GetEvenIfUnreachable()) ++RemainingOldMuzzles;
        int32 FighterMaterials = 0;
        for (TObjectIterator<UMaterialInstanceDynamic> Material; Material; ++Material)
        {
            const ATempleFighter* Owner = Material->GetTypedOuter<ATempleFighter>();
            if (Owner && Owner->GetWorld() == World) ++FighterMaterials;
        }
        const FPlatformMemoryStats Memory = FPlatformMemory::GetStats();
        FGenericMemoryStats Allocator;
        UE::Private::GMalloc->GetAllocatorStats(Allocator);
        const SIZE_T* UsedHeap = Allocator.Find(TEXT("TotalAllocated"));
        const SIZE_T* ReservedHeap = Allocator.Find(TEXT("TotalOSAllocated"));
        int32 ActiveSounds = 0;
        if (const FAudioDeviceHandle Device = World->GetAudioDevice())
        {
            FAudioThread::RunCommandOnAudioThread([Device, &ActiveSounds] { ActiveSounds = Device->GetActiveSounds().Num(); });
            FAudioCommandFence AudioFence;
            AudioFence.BeginFence();
            AudioFence.Wait();
        }
        const FString Row = FString::Printf(
            TEXT("%d,%s,%.2f,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%.2f,%.2f,%d,%d,%d,%d,%d,%d,%.2f,%.2f,%d,%d,%d,%d,%d,%d,%d,%d,%d\n"),
            Round, Stage, World->GetTimeSeconds(), Match->RedScore, Match->BlueScore, Match->Phase,
            CountWorldInstances<ATempleFighter>(World), CountWorldInstances<ATempleBotController>(World),
            CountWorldInstances<ATemplePlayerController>(World), Match->PlayerArray.Num(), CountWorldInstances<UTempleCombatHUD>(World),
            CountWorldInstances<UUserWidget>(World), CountWorldInstances<UWidget>(World), FX.Total, FX.Active,
            PeakFX, PeakActiveFX, CountWorldInstances<UAudioComponent>(World), CountWorldInstances<USkeletalMeshComponent>(World),
            CountWorldInstances<UStaticMeshComponent>(World), FighterMaterials,
            double(Memory.UsedPhysical) / 1048576., double(Memory.UsedVirtual) / 1048576.,
            GUObjectArray.GetObjectArrayNumMinusAvailable(), RemainingOldPawns, int32(bMenuOpened), int32(bRosterOpened),
            Match->FinalStandings.Num(), ActiveSounds, UsedHeap ? double(*UsedHeap) / 1048576. : -1.,
            ReservedHeap ? double(*ReservedHeap) / 1048576. : -1.,
            FX.Muzzles, FX.UniqueOwners, FX.ActiveMuzzles, FX.UnownedMuzzles, PeakDuplicateMuzzles,
            PeakActiveMuzzles, RemainingOldMuzzles, HighestActiveClock, RoundDuration);
        FFileHelper::SaveStringToFile(Row, *Output, FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM, &IFileManager::Get(), FILEWRITE_Append);
    }

    bool SampleRound(UWorld* World, ATempleGameState* Match, ATemplePlayerController* Player)
    {
        const double Now = FPlatformTime::Seconds();
        if (bAwaitingPurge)
        {
            if (Purges <= RequestedPurge) return true;
            Record(World, Match, TEXT("replay_post_gc"));
            UE_LOG(LogTemp, Display, TEXT("TempleLifetime_RHI after replay %d"), Round);
            GEngine->Exec(World, TEXT("rhi.DumpMemory"));
            PreviousPawns.Reset();
            PreviousMuzzles.Reset();
            bAwaitingPurge = false;
            if (Round == 8)
            {
                Player->QuitGame();
                return false;
            }
            ++Round;
            PeakFX = PeakActiveFX = PeakActiveMuzzles = PeakDuplicateMuzzles = HighestActiveClock = MenuStep = 0;
            bMenuOpened = bRosterOpened = false;
            EndedAt = -1;
        }
        if (Match->Phase == 2)
        {
            RoundDuration = FMath::CeilToInt32(Match->PhaseDuration);
            HighestActiveClock = FMath::Max(HighestActiveClock, Match->RemainingPhaseSeconds(Match->GetServerWorldTimeSeconds()));
            if (Now >= NextPeak)
            {
                NextPeak = Now + .25;
                const FParticleCounts FX = CountParticles(World);
                PeakFX = FMath::Max(PeakFX, FX.Total);
                PeakActiveFX = FMath::Max(PeakActiveFX, FX.Active);
                PeakActiveMuzzles = FMath::Max(PeakActiveMuzzles, FX.ActiveMuzzles);
                PeakDuplicateMuzzles = FMath::Max(PeakDuplicateMuzzles, FX.DuplicateMuzzles());
            }
            if (MenuStep == 0)
            {
                Player->SetMenuOpen(true);
                bMenuOpened = Player->bMenuOpen;
                MenuOpenedAt = Now;
                MenuStep = 1;
            }
            else if (MenuStep == 1 && Now > MenuOpenedAt + .25)
            {
                Player->SetMenuOpen(false);
                Player->SetScoreboardVisible(true);
                bRosterOpened = Player->bScoreboardVisible;
                MenuStep = 2;
            }
            else if (MenuStep == 2 && Now > MenuOpenedAt + .55)
            {
                Player->SetScoreboardVisible(false);
                MenuStep = 3;
            }
        }
        if (Match->Phase == 3)
        {
            if (EndedAt < 0) EndedAt = Now;
            if (Now < EndedAt + .8) return true;
            for (TActorIterator<ATempleFighter> Fighter(World); Fighter; ++Fighter) PreviousPawns.Add(*Fighter);
            CountParticles(World, &PreviousMuzzles);
            Record(World, Match, TEXT("match_end"));
            Player->ReplayMatch();
            Record(World, Match, TEXT("replay_pre_gc"));
            RequestedPurge = Purges;
            bAwaitingPurge = true;
            GEngine->ForceGarbageCollection(true);
        }
        return true;
    }
};
TUniquePtr<FTempleLifetimeRecorder> LifetimeRecorder;
}

void StartTempleLifetimeReview()
{
    FString Output;
    if (!FParse::Value(FCommandLine::Get(), TEXT("TempleLifetime="), Output)) return;
    LifetimeRecorder = MakeUnique<FTempleLifetimeRecorder>();
    LifetimeRecorder->Output = Output;
    const FString Header = TEXT("round,stage,world_seconds,red,blue,phase,fighters,bots,humans,player_states,huds,user_widgets,widgets,niagara,active_niagara,peak_niagara,peak_active_niagara,audio_components,skinned_components,static_components,fighter_dynamic_materials,working_set_mib,private_commit_mib,global_objects,retired_pawns_still_allocated,opened_menu,opened_roster,final_standings,active_mixer_sounds,ue_heap_mib,ue_heap_reserved_mib,muzzles,muzzle_owners,active_muzzles,unowned_muzzles,peak_duplicate_muzzles,peak_active_muzzles,retired_muzzles_still_allocated,highest_active_clock,round_duration\n");
    FFileHelper::SaveStringToFile(Header, *Output, FFileHelper::EEncodingOptions::ForceUTF8WithoutBOM);
    LifetimeRecorder->PurgeHandle = FCoreUObjectDelegates::GetPostPurgeGarbageDelegate().AddLambda([] { ++LifetimeRecorder->Purges; });
    LifetimeRecorder->TickHandle = FTSTicker::GetCoreTicker().AddTicker(FTickerDelegate::CreateLambda([](float) { return LifetimeRecorder->Tick(); }));
}

void StopTempleLifetimeReview()
{
    if (!LifetimeRecorder) return;
    FTSTicker::GetCoreTicker().RemoveTicker(LifetimeRecorder->TickHandle);
    FCoreUObjectDelegates::GetPostPurgeGarbageDelegate().Remove(LifetimeRecorder->PurgeHandle);
    LifetimeRecorder.Reset();
}
#endif
