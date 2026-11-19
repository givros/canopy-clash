#include "Modules/ModuleManager.h"

#if PLATFORM_WASM
#include "DeviceProfiles/DeviceProfileManager.h"
#include "Engine/Engine.h"
#include "HAL/IConsoleManager.h"
#include "HAL/PlatformMemory.h"
#include "Misc/App.h"
#include "Misc/CommandLine.h"
#include "Misc/ConfigCacheIni.h"
#include "Misc/CoreDelegates.h"
#include "Misc/Parse.h"
#include "WasmPageBridge.h"
void StartTempleWebStreaming();
void StopTempleWebStreaming();

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

// Transient settings only. The ceiling comes from the size of the actual canvas;
// manual URL, renderer and saved quality choices never enter this controller.
class FTempleWebFrameBudget
{
public:
    void Start()
    {
        const TCHAR* Cmd = FCommandLine::Get();
        if (!FParse::Value(Cmd, TEXT("CanopyWebAdaptive="), Ceiling) ||
            Ceiling < 25 || Ceiling > 100 || GConfig->DoesSectionExist(TEXT("ScalabilityGroups"), GGameUserSettingsIni)) return;
        Floor = FMath::Max(25, FMath::RoundToInt(Ceiling * .75f));
        bMobile = FParse::Param(Cmd, TEXT("CanopyWebHandheld"));
        Resolution = IConsoleManager::Get().FindConsoleVariable(TEXT("r.ScreenPercentage"));
        if (!Resolution) return;
        bGpuTiming = FParse::Param(Cmd, TEXT("CanopyWebGpuTiming"));
        if (bGpuTiming)
        {
            SetCVar(TEXT("r.DynamicRes.MinScreenPercentage"), Floor);
            SetCVar(TEXT("r.DynamicRes.MaxScreenPercentage"), Ceiling);
            SetCVar(TEXT("r.DynamicRes.FrameTimeBudget"), 16.67f);
            SetCVar(TEXT("r.DynamicRes.MinResolutionChangePeriod"), 30);
            SetCVar(TEXT("r.DynamicRes.OperationMode"), 2);
        }
        FrameHandle = FCoreDelegates::OnEndFrame.AddRaw(this, &FTempleWebFrameBudget::OnFrame);
        printf("CANOPY_FRAME_BUDGET %d..%d%% %s\n", Floor, Ceiling, bGpuTiming ? "gpu timed" : "frame timed");
    }
    void Stop() { FCoreDelegates::OnEndFrame.Remove(FrameHandle); }

private:
    static void SetCVar(const TCHAR* Name, float Value)
    {
        if (IConsoleVariable* Var = IConsoleManager::Get().FindConsoleVariable(Name))
            Var->Set(Value, ECVF_SetByGameSetting);
    }

    void OnFrame()
    {
        if (!FWasmPageBridge::IsReady() || !GEngine) return;
        const double Now = FPlatformTime::Seconds();
        const double Delta = Now - LastFrame;
        LastFrame = Now;
        // Ignore loading, a hidden tab and isolated freezes. A pause to fetch
        // content must not permanently turn down the image quality.
        if (Delta <= 0 || Delta > .20)
        {
            SampleSeconds = 0;
            Samples = Late = Easy = SlowWindows = FastWindows = 0;
            return;
        }
        const double Work = bCapped ? FMath::Max(0., Delta - FApp::GetIdleTime()) : Delta;
        ++Samples;
        if (Work > .023) ++Late;
        if (Work < .018) ++Easy;
        SampleSeconds += Delta;
        if (SampleSeconds < 2.5) return;
        SlowWindows = Late > Samples * .55 ? SlowWindows + 1 : 0;
        FastWindows = Easy > Samples * .90 ? FastWindows + 1 : 0;
        const bool bVerySlow = SampleSeconds / Samples > .026;
        SampleSeconds = 0;
        Samples = Late = Easy = 0;

        FDynamicResolutionStateInfos DynamicState;
        GEngine->GetDynamicResolutionCurrentStateInfos(DynamicState);
        const bool bUsingGpuTiming = bGpuTiming && DynamicState.Status == EDynamicResolutionStatus::Enabled;
        if (!bUsingGpuTiming && !bCapped)
        {
            int32 Scale = FMath::RoundToInt(Resolution->GetFloat());
            if (Scale <= 0) Scale = Ceiling;
            const int32 Next = SlowWindows >= 2 ? FMath::Max(Floor, Scale - 8) :
                FastWindows >= 4 ? FMath::Min(Ceiling, Scale + 4) : Scale;
            if (Next != Scale)
            {
                Resolution->SetWithCurrentPriority(Next);
                printf("CANOPY_FRAME_BUDGET scale %d%%\n", Next);
                if (Next > Scale) FastWindows = 0;
                else SlowWindows = 0;
            }
        }
        // On a phone that cannot sustain 60 Hz even after several seconds of
        // adaptation, pace at 30. Restore the higher ceiling after several
        // windows of spare processing time (excluding deliberate frame sleep).
        if (bMobile && !bCapped && SlowWindows >= 4 && bVerySlow)
        {
            PreviousCap = GEngine->GetMaxFPS();
            if (PreviousCap == 0 || PreviousCap > 30)
            {
                GEngine->SetMaxFPS(30);
                if (bGpuTiming) SetCVar(TEXT("r.DynamicRes.FrameTimeBudget"), 33.33f);
                bCapped = true;
                printf("CANOPY_FRAME_BUDGET cap 30\n");
            }
            SlowWindows = 0;
        }
        else if (bCapped && FastWindows >= 6 && FMath::IsNearlyEqual(GEngine->GetMaxFPS(), 30.f))
        {
            GEngine->SetMaxFPS(PreviousCap);
            if (bGpuTiming) SetCVar(TEXT("r.DynamicRes.FrameTimeBudget"), 16.67f);
            bCapped = false;
            FastWindows = 0;
            printf("CANOPY_FRAME_BUDGET cap restored\n");
        }
    }

    FDelegateHandle FrameHandle;
    IConsoleVariable* Resolution = nullptr;
    double LastFrame = 0, SampleSeconds = 0;
    int32 Ceiling = 100, Floor = 75, Samples = 0, Late = 0, Easy = 0, SlowWindows = 0, FastWindows = 0;
    float PreviousCap = 0;
    bool bMobile = false, bGpuTiming = false, bCapped = false;
};
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
    FTempleWebFrameBudget FrameBudget;
    FDelegateHandle FrameBudgetHandle;
#endif
public:
    virtual void StartupModule() override
    {
#if PLATFORM_WASM
        WebTexturePoolHandle = FCoreDelegates::GetOnPostEngineInit().AddStatic(ApplyDesktopWebTexturePool);
        StartTempleWebStreaming();
        FrameBudgetHandle = FCoreDelegates::GetOnPostEngineInit().AddRaw(&FrameBudget, &FTempleWebFrameBudget::Start);
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
        StopTempleWebStreaming();
        FCoreDelegates::GetOnPostEngineInit().Remove(FrameBudgetHandle);
        FrameBudget.Stop();
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
