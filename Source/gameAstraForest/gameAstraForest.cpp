#include "Modules/ModuleManager.h"

#if PLATFORM_WASM
#include "DeviceProfiles/DeviceProfileManager.h"
#include "HAL/IConsoleManager.h"
#include "HAL/PlatformMemory.h"
#include "Misc/CommandLine.h"
#include "Misc/CoreDelegates.h"
#include "Misc/Parse.h"

static void ApplyDesktopWebTexturePool()
{
    int32 RequestedMiB = 0;
    if (!FParse::Value(FCommandLine::Get(), TEXT("TempleWebTexturePool="), RequestedMiB)) return;

    const TCHAR* PoolName = TEXT("r.Streaming.PoolSize");
    IConsoleVariable* Pool = IConsoleManager::Get().FindConsoleVariable(PoolName);
    // Only extend the automatic mobile-renderer cap. Preserve explicit ini,
    // console and device-profile values at their original priority.
    if (!Pool || Pool->GetInt() != 192 || (Pool->GetFlags() & ECVF_SetByMask) != ECVF_SetByDeviceProfile) return;
    const FString ProfileName = UDeviceProfileManager::Get().GetActiveDeviceProfileName();
    const auto ProfileCVars = UDeviceProfileManager::GatherDeviceProfileCVars(
        { &ProfileName, UDeviceProfileManager::EDeviceProfileMode::DPM_CacheValues });
    if (ProfileCVars.Contains(FName(PoolName))) return;

    const int32 HeapBudgetMiB = static_cast<int32>(FPlatformMemory::GetConstants().TotalPhysical / (6 * 1024 * 1024));
    const int32 BudgetMiB = FMath::Min3(RequestedMiB, HeapBudgetMiB, 640) & ~15;
    if (BudgetMiB > Pool->GetInt())
    {
        Pool->Set(BudgetMiB, ECVF_SetByDeviceProfile);
        UE_LOG(LogTemp, Display, TEXT("Canopy Clash desktop texture budget: %d MiB"), BudgetMiB);
    }
}
#endif

#if !UE_BUILD_SHIPPING
void StartTempleMatchAudit();
void StopTempleMatchAudit();
void StartTempleLifetimeReview();
void StopTempleLifetimeReview();
void StartTemplePrivateReview();
void StopTemplePrivateReview();
void StartTempleDuel();
void StopTempleDuel();
void StartTempleVisualReview();
void StopTempleVisualReview();
void StartTempleHandlingReview();
void StopTempleHandlingReview();
void StartTempleBalanceReview();
void StopTempleBalanceReview();
void StartTempleUIInputAudit();
void StopTempleUIInputAudit();
void StartTempleAudioReview();
void StopTempleAudioReview();
void StartTempleLatencyReview();
void StopTempleLatencyReview();
void StartTempleTraversalReview();
void StopTempleTraversalReview();
void StartTempleCrowdReview();
void StopTempleCrowdReview();
#endif

class FTempleGameModule : public FDefaultGameModuleImpl
{
#if PLATFORM_WASM
    FDelegateHandle WebTexturePoolHandle;
#endif
public:
    virtual void StartupModule() override
    {
#if PLATFORM_WASM
        WebTexturePoolHandle = FCoreDelegates::GetOnPostEngineInit().AddStatic(ApplyDesktopWebTexturePool);
#endif
#if !UE_BUILD_SHIPPING
        StartTempleMatchAudit();
        StartTempleLifetimeReview();
        StartTemplePrivateReview();
        StartTempleDuel();
        StartTempleVisualReview();
        StartTempleHandlingReview();
        StartTempleBalanceReview();
        StartTempleUIInputAudit();
        StartTempleAudioReview();
        StartTempleLatencyReview();
        StartTempleTraversalReview();
        StartTempleCrowdReview();
#endif
    }
    virtual void ShutdownModule() override
    {
#if PLATFORM_WASM
        FCoreDelegates::GetOnPostEngineInit().Remove(WebTexturePoolHandle);
#endif
#if !UE_BUILD_SHIPPING
        StopTempleMatchAudit();
        StopTempleLifetimeReview();
        StopTemplePrivateReview();
        StopTempleDuel();
        StopTempleVisualReview();
        StopTempleHandlingReview();
        StopTempleBalanceReview();
        StopTempleUIInputAudit();
        StopTempleAudioReview();
        StopTempleLatencyReview();
        StopTempleTraversalReview();
        StopTempleCrowdReview();
#endif
    }
};
IMPLEMENT_PRIMARY_GAME_MODULE(FTempleGameModule, gameAstraForest, "gameAstraForest");
