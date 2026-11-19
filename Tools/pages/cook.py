"""Cook the WebGPU map with distance LODs for its non-Nanite foliage."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

MESH_FOLDER = Path("Content/AstraTemple/Nature/Meshes")
PLANTS = ("SM_Fern", "SM_Monstera", "SM_ArecaPalm", "SM_CecropiaSapling", "SM_LianaCurtain", "SM_MossCushion")
LEVELS = ((1.0, 1.0), (0.45, 0.18), (0.16, 0.065), (0.055, 0.028))


def prepare_meshes(unreal):
    root = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()))
    overlay = Path(os.environ["CANOPY_WEB_COOK_OVERLAY"])
    probe = root / MESH_FOLDER / "canopy-mount-check.txt"
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
    (overlay / "ready").touch()


def cook(editor, project):
    root = project.parent
    source = root / MESH_FOLDER
    release = root / "Saved/PagesRelease"
    release.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="foliage-", dir=release) as temporary:
        overlay = Path(temporary)
        for name in PLANTS:
            shutil.copyfile(source / (name + ".uasset"), overlay / (name + ".uasset"))
        (overlay / "canopy-mount-check.txt").touch()
        # Both commandlets see the same package names. Other assets are read from the project.
        mount = "-InjectionSandbox=" + source.as_posix() + ";" + overlay.as_posix()
        common = [editor, project, mount, "-nullrhi", "-unattended", "-nop4", "-nosplash"]
        env = dict(os.environ, CANOPY_WEB_COOK_OVERLAY=str(overlay))
        subprocess.run([*common, "-run=pythonscript", "-script=" + str(Path(__file__).resolve()),
                        "-NoShaderCompile"], env=env, check=True)
        if not (overlay / "ready").is_file():
            raise RuntimeError("Unreal did not finish the foliage build.")
        subprocess.run([*common, "-run=Cook", "-TargetPlatform=Wasm", "-CookCultures=en",
                        "-Map=/Game/AstraTemple/Maps/L_CanopyDeathmatch", "-NoAlwaysCookMaps"], check=True)


if __name__ == "__main__":
    if os.environ.get("CANOPY_WEB_COOK_OVERLAY"):
        import unreal
        prepare_meshes(unreal)
    else:
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument("--editor", required=True, type=Path)
        parser.add_argument("--project", required=True, type=Path)
        args = parser.parse_args()
        cook(args.editor.resolve(), args.project.resolve())
