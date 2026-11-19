using UnrealBuildTool;

public class gameAstraForestEditorTarget : TargetRules
{
    public gameAstraForestEditorTarget(TargetInfo Target) : base(Target)
    {
        Type = TargetType.Editor;
        DefaultBuildSettings = BuildSettingsVersion.V8;
        IncludeOrderVersion = EngineIncludeOrderVersion.Unreal5_9;
        ExtraModuleNames.Add("gameAstraForest");
    }
}
