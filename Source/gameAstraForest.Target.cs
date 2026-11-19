using UnrealBuildTool;

public class gameAstraForestTarget : TargetRules
{
    public gameAstraForestTarget(TargetInfo Target) : base(Target)
    {
        Type = TargetType.Game;
        DefaultBuildSettings = BuildSettingsVersion.V8;
        IncludeOrderVersion = EngineIncludeOrderVersion.Unreal5_9;
        ExtraModuleNames.Add("gameAstraForest");
    }
}
