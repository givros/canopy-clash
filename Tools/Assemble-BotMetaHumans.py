"""Run from the Unreal Editor Python console to assemble the game's five bot actors."""

import gc

import unreal


BOT_ROOT = "/Game/TempleTDM/Bots"
CHARACTERS = {
    "Hannah": "/Game/EditableCharacters/MHC_Hannah/MHC_Hannah",
    "Kabir": "/Game/EditableCharacters/MHC_Kabir/MHC_Kabir",
    "Hero1": "/Game/Fab/MetaHuman/MHC_Hero",
    "Advika": "/Game/Fab/MetaHuman/MHC_Advika",
    "Dean": "/Game/Fab/MetaHuman/Dean",
}


def assemble(name, rebuild=False):
    """Build one existing MetaHuman using Epic's local UE Optimized pipeline."""
    source = CHARACTERS[name]
    directory = f"{BOT_ROOT}/{name}"
    blueprint = f"{directory}/BP_{name}"
    assets = unreal.EditorAssetLibrary
    if assets.does_asset_exist(blueprint) and not rebuild:
        return blueprint

    character = unreal.load_asset(source)
    subsystem = unreal.get_editor_subsystem(unreal.MetaHumanCharacterEditorSubsystem)
    if not character:
        raise RuntimeError(f"Missing source character {source}")
    was_open = subsystem.is_object_added_for_editing(character)
    if not was_open and not subsystem.try_add_object_to_edit(character):
        raise RuntimeError(f"Could not open {source}")
    try:
        params = unreal.MetaHumanCharacterEditorBuildParameters()
        params.pipeline_type = unreal.MetaHumanDefaultPipelineType.OPTIMIZED
        params.pipeline_quality = unreal.MetaHumanQualityLevel.MEDIUM
        params.absolute_build_path = BOT_ROOT
        params.common_folder_path = f"{BOT_ROOT}/Common"
        params.name_override = name
        params.enable_wardrobe_item_validation = False
        try:
            if subsystem.can_build_meta_human(character, False):
                subsystem.build_meta_human(character, params)
            elif name == "Hero1":
                # The Fab artist supplies this character with a fitted neutral
                # face and no independent facial performance rig.
                world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
                unreal.SystemLibrary.execute_console_command(
                    world, f"Temple.AssembleNeutralBot {character.get_path_name()} {name}"
                )
            else:
                raise RuntimeError(f"{name} is missing MetaHuman assembly prerequisites")
        except RuntimeError as error:
            # UE 5.9 can surface an editor control-board upgrade message after
            # completing the assembly. The generated actor is validated below.
            if "Face_ControlBoard_CtrlRig : Cannot break link" not in str(error):
                raise
            unreal.log_warning(str(error))
        generated_class = assets.load_blueprint_class(blueprint)
        if not generated_class:
            raise RuntimeError(f"Assembly did not produce {blueprint}")

        actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        actor = actors.spawn_actor_from_class(generated_class, unreal.Vector(), unreal.Rotator(), True)
        if not actor:
            raise RuntimeError(f"Could not instantiate {blueprint}")
        try:
            components = actor.get_components_by_class(unreal.SkinnedMeshComponent)
            skinned = {c.get_name(): c.get_skinned_asset() for c in components}
            if not skinned.get("Body") or not skinned.get("Face"):
                raise RuntimeError(f"Missing fitted face or body in {blueprint}")
            outfit = [mesh for part, mesh in skinned.items() if mesh and part not in ("Body", "Face")]
            if len(outfit) < 2:
                raise RuntimeError(f"Missing clothing or footwear in {blueprint}")
        finally:
            actors.destroy_actor(actor)

        for path in (params.common_folder_path, directory):
            if not assets.save_directory(path, True, True):
                raise RuntimeError(f"Could not save assembled assets in {path}")
        return blueprint
    finally:
        if not was_open:
            subsystem.remove_object_to_edit(character)
        gc.collect()
        unreal.SystemLibrary.collect_garbage()


if __name__ == "__main__":
    for bot_name in CHARACTERS:
        unreal.log(assemble(bot_name))
