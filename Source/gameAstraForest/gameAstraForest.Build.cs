using UnrealBuildTool;

public class gameAstraForest : ModuleRules
{
    public gameAstraForest(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
        PublicDependencyModuleNames.AddRange(new[]
        {
            "Core", "CoreUObject", "Engine", "InputCore", "EnhancedInput",
            "AIModule", "NavigationSystem", "GameplayTasks", "UMG", "NetCore", "OnlineSubsystemUtils", "Sockets"
        });
        PrivateDependencyModuleNames.AddRange(new[] { "Slate", "SlateCore", "Niagara", "Landscape", "Networking", "AnimationCore" });
        if (Target.Configuration != UnrealTargetConfiguration.Shipping)
            PrivateDependencyModuleNames.Add("AudioMixer");
        if (Target.bBuildEditor)
        {
            PrivateDependencyModuleNames.AddRange(new[] { "AnimGraph", "AnimGraphRuntime", "BlueprintGraph", "Kismet", "UnrealEd",
                "MetaHumanCharacter", "MetaHumanCharacterPalette", "MetaHumanCharacterEditor" });
        }
    }
}
