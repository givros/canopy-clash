#if PLATFORM_WASM
#include "Containers/Ticker.h"
#include "Engine/Engine.h"
#include "HAL/IConsoleManager.h"
#include "Misc/CommandLine.h"
#include "Misc/ConfigCacheIni.h"
#include "Misc/Parse.h"
#include <atomic>
#include <cstdio>
#include <emscripten/emscripten.h>

namespace
{
    std::atomic<bool> Constrained{false};
    FTSTicker::FDelegateHandle TickHandle;
    float NormalBias = 0;
    bool Adjusted = false;

    bool UpdateTextureBias(float)
    {
        if (!GEngine || Constrained.load() == Adjusted) return true;
        static IConsoleVariable* Bias = IConsoleManager::Get().FindConsoleVariable(TEXT("r.Streaming.MipBias"));
        if (!Bias) return true;
        if (Constrained.load())
        {
            NormalBias = Bias->GetFloat();
            Bias->SetWithCurrentPriority(NormalBias + 1.f);
            Adjusted = true;
        }
        else
        {
            if (FMath::IsNearlyEqual(Bias->GetFloat(), NormalBias + 1.f))
                Bias->SetWithCurrentPriority(NormalBias);
            Adjusted = false;
        }
        std::printf("CANOPY_TEXTURE_STREAM mip bias %.1f\n", Bias->GetFloat());
        return true;
    }
}

// Browser callbacks may run before the engine, or on a different thread.
extern "C" EMSCRIPTEN_KEEPALIVE void CanopySetNetworkPressure(int Value)
{
    Constrained.store(Value != 0);
}

void StartTempleWebStreaming()
{
    int32 Ceiling = 0;
    if (!FParse::Value(FCommandLine::Get(), TEXT("CanopyWebAdaptive="), Ceiling) ||
        (GConfig && GConfig->DoesSectionExist(TEXT("ScalabilityGroups"), GGameUserSettingsIni))) return;
    TickHandle = FTSTicker::GetCoreTicker().AddTicker(FTickerDelegate::CreateStatic(&UpdateTextureBias), 1.f);
}

void StopTempleWebStreaming()
{
    FTSTicker::GetCoreTicker().RemoveTicker(TickHandle);
}
#endif
