#if WITH_EDITOR
#include "HAL/IConsoleManager.h"
#include "MetaHumanCharacter.h"
#include "MetaHumanCharacterEditorSubsystem.h"
#include "MetaHumanCharacterPaletteProjectSettings.h"
#include "MetaHumanCollectionPipeline.h"
#include "Subsystem/MetaHumanCharacterBuild.h"

namespace
{
// For body-driven NPCs, bake the character's fitted neutral head and authored wardrobe.
// An independent facial performance rig is optional in this game.
void AssembleNeutralBot(const TArray<FString>& Arguments)
{
    if (Arguments.Num()!=2) return;
    auto* Character=LoadObject<UMetaHumanCharacter>(nullptr,*Arguments[0]);
    auto* Editor=UMetaHumanCharacterEditorSubsystem::Get();
    if (!Character || !Editor || !Editor->IsObjectAddedForEditing(Character) || !Character->HasHighResolutionTextures())
    {
        UE_LOG(LogTemp,Error,TEXT("Bot assembly needs an open MetaHuman character with its texture sources"));
        return;
    }
    FMetaHumanCharacterEditorBuildParameters Params;
    Params.PipelineType=EMetaHumanDefaultPipelineType::Optimized;
    Params.PipelineQuality=EMetaHumanQualityLevel::Medium;
    Params.AbsoluteBuildPath=TEXT("/Game/TempleTDM/Bots");
    Params.CommonFolderPath=Params.AbsoluteBuildPath/TEXT("Common");
    Params.NameOverride=Arguments[1];
    Params.bEnableWardrobeItemValidation=false;
    const auto* Medium=GetDefault<UMetaHumanCharacterPaletteProjectSettings>()->DefaultCharacterLegacyPipelines.Find(Params.PipelineQuality);
    UClass* PipelineClass=Medium ? Medium->LoadSynchronous() : nullptr;
    if (!PipelineClass) return;
    Params.PipelineOverride=NewObject<UMetaHumanCollectionPipeline>(Character,PipelineClass);
    FMetaHumanCharacterEditorBuild::BuildMetaHumanCharacter(Character,Params);
}
FAutoConsoleCommand NeutralBotAssembly(TEXT("Temple.AssembleNeutralBot"),TEXT("Bake a body-driven bot from an open MetaHuman. Arguments: asset path and appearance name."),
    FConsoleCommandWithArgsDelegate::CreateStatic(&AssembleNeutralBot));
}
#endif
