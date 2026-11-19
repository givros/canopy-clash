"""Unreal Editor Python. Import original mono steps and a mono edit of the project template report."""
from pathlib import Path
import unreal


source = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())) / "ArtSource/TempleTDM/Feedback/Footsteps"
tools = unreal.AssetToolsHelpers.get_asset_tools()
results = []
for wav in sorted(source.glob("S_*.wav")):
    step = wav.stem.startswith("S_Step")
    task = unreal.AssetImportTask()
    task.set_editor_properties(dict(filename=str(wav), destination_path="/Game/TempleTDM/Feedback" + ("/Footsteps" if step else ""), automated=True, replace_existing=True, save=True))
    tools.import_asset_tasks([task])
    wave = unreal.load_asset(task.imported_object_paths[0])
    wave.set_editor_property("volume", 1.0 if step else .61)
    wave.set_editor_property("loading_behavior", unreal.SoundWaveLoadingBehavior.FORCE_INLINE)
    unreal.EditorAssetLibrary.save_loaded_asset(wave, False)
    results.append([wave.get_path_name(), wave.duration, wave.get_editor_property("num_channels"), wave.get_editor_property("volume")])
results
