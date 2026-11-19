"""Cook the WebGPU map with web texture budgets and distance LODs."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

MESH_FOLDER = Path("AstraTemple/Nature/Meshes")
PLANTS = ("SM_Fern", "SM_Monstera", "SM_ArecaPalm", "SM_CecropiaSapling", "SM_LianaCurtain", "SM_MossCushion")
LEVELS = ((1.0, 1.0), (0.45, 0.18), (0.16, 0.065), (0.055, 0.028))


def prepare_assets(unreal):
    root = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()))
    overlay = Path(os.environ["CANOPY_WEB_COOK_OVERLAY"])
    content = root / "Content"
    probe = content / "canopy-mount-check.txt"
    if probe.exists() or not unreal.Paths.file_exists(probe.as_posix()):
        raise RuntimeError("Unreal did not mount the temporary mesh directory.")
    editor = unreal.get_default_object(unreal.StaticMeshEditorSubsystem)
    options = unreal.StaticMeshReductionOptions()
    options.set_editor_property("auto_compute_lod_screen_size", False)
    options.set_editor_property("reduction_settings", [
        unreal.StaticMeshReductionSettings(percent_triangles=fraction, screen_size=size)
        for fraction, size in LEVELS
    ])
    for name in PLANTS:
        mesh = unreal.load_asset("/Game/AstraTemple/Nature/Meshes/" + name)
        if not mesh:
            raise RuntimeError("Missing foliage mesh " + name)
        if editor.get_lod_count(mesh) > 1:
            continue  # An artist's existing LOD chain takes precedence.
        near_vertices = editor.get_number_verts(mesh, 0)
        if editor.set_lods(mesh, options) < 0 or editor.get_lod_count(mesh) != len(LEVELS):
            raise RuntimeError("Could not build the web LODs for " + name)
        if editor.get_number_verts(mesh, 0) != near_vertices or not 0 < editor.get_number_verts(mesh, 3) < near_vertices:
            raise RuntimeError("Unexpected foliage geometry for " + name)
        if not unreal.EditorAssetLibrary.save_loaded_asset(mesh, only_if_is_dirty=False):
            raise RuntimeError("Could not save the web LODs for " + name)
    registry = unreal.AssetRegistryHelpers.get_asset_registry()
    registry.wait_for_completion()
    changed = 0
    # Only the browser cook sees these edits. Keep the principal terrain, facial
    # and weapon maps at 2K. Cloth weave and individual plants occupy a much
    # smaller portion of the screen, including in a close combat encounter.
    for folder in ("/Game/AstraTemple", "/Game/TempleTDM/Bots", "/Game/Fab"):
        for asset in registry.get_assets_by_path(folder, recursive=True):
            if str(asset.asset_class_path.asset_name) not in ("Texture2D", "TextureCube"):
                continue
            name = str(asset.package_name)
            group = str(asset.get_tag_value("LODGroup") or "")
            if group in ("TEXTUREGROUP_UI", "TEXTUREGROUP_Pixels2D"):
                continue
            limited = (name.startswith(("/Game/AstraTemple/FloraStudies/", "/Game/AstraTemple/Nature/")) or
                       (("/Bots/" in name or "/Fab/" in name) and
                        any(part in name for part in ("/Clothing/", "/Hair/", "/HairCards/", "/CasualSneakers/"))))
            cap = 1024 if limited else 2048
            dimensions = str(asset.get_tag_value("Dimensions") or "").split("x")
            if not all(n.isdigit() for n in dimensions) or max(map(int, dimensions)) <= cap:
                continue
            relative = Path(name.removeprefix("/Game/") + ".uasset")
            destination = overlay / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(content / relative, destination)
            texture = asset.get_asset()
            before = texture.get_editor_property("max_texture_size")
            if 0 < before <= cap:
                continue
            texture.set_editor_property("max_texture_size", cap)
            if not unreal.EditorAssetLibrary.save_loaded_asset(texture, only_if_is_dirty=False):
                raise RuntimeError("Could not save the web texture limit for " + name)
            changed += 1
            if changed % 20 == 0:
                unreal.SystemLibrary.collect_garbage()
    unreal.log("Canopy web cook capped " + str(changed) + " textures in its overlay.")
    (overlay / "ready").touch()


def cook(editor, project, targets):
    root = project.parent
    source = root / "Content"
    release = root / "Saved/PagesRelease"
    release.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="foliage-", dir=release) as temporary:
        overlay = Path(temporary)
        (overlay / MESH_FOLDER).mkdir(parents=True)
        for name in PLANTS:
            relative = MESH_FOLDER / (name + ".uasset")
            shutil.copyfile(source / relative, overlay / relative)
        (overlay / "canopy-mount-check.txt").touch()
        # Both commandlets see the same package names. Other assets are read from the project.
        mount = "-InjectionSandbox=" + source.as_posix() + ";" + overlay.as_posix()
        common = [editor, project, mount, "-nullrhi", "-unattended", "-nop4", "-nosplash"]
        env = dict(os.environ, CANOPY_WEB_COOK_OVERLAY=str(overlay))
        subprocess.run([*common, "-run=pythonscript", "-script=" + str(Path(__file__).resolve()),
                        "-NoShaderCompile"], env=env, check=True)
        if not (overlay / "ready").is_file():
            raise RuntimeError("Unreal did not finish the foliage build.")
        # Match UAT's native Wasm_ASTC block sizes. WebGPU cannot upload the
        # engine's default 6x6 color blocks at power-of-two image dimensions.
        for target in targets:
            texture_options = []
            if target == "Wasm_ASTC":
                texture_options = ["-ini:Engine:[/Script/UnrealEd.CookerSettings]:DefaultASTCQualityBySize=2",
                                   "-ini:Engine:[/Script/UnrealEd.CookerSettings]:DefaultASTCQualityBySizeHQ=4"]
            subprocess.run([*common, "-run=Cook", "-TargetPlatform=" + target, "-CookCultures=en",
                            "-Map=/Game/AstraTemple/Maps/L_CanopyDeathmatch", "-NoAlwaysCookMaps",
                            *texture_options], check=True)
            print("Finished web cook " + target, flush=True)


if __name__ == "__main__":
    if os.environ.get("CANOPY_WEB_COOK_OVERLAY"):
        import unreal
        prepare_assets(unreal)
    else:
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument("--editor", required=True, type=Path)
        parser.add_argument("--project", required=True, type=Path)
        parser.add_argument("--target", nargs="+", choices=("Wasm", "Wasm_ASTC"), default=["Wasm"])
        args = parser.parse_args()
        cook(args.editor.resolve(), args.project.resolve(), args.target)
