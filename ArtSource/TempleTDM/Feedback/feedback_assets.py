"""Create the arena's native Unreal feedback assets and the two editable animation graphs."""
from pathlib import Path
import unreal as u

HERE = Path(__file__).resolve().parent
DEST = "/Game/TempleTDM/Feedback"
ANIM = "/Game/TempleTDM/Animation"
assets = u.EditorAssetLibrary
tools = u.AssetToolsHelpers.get_asset_tools()

def save(asset):
    if not assets.save_loaded_asset(asset, False):
        raise RuntimeError("Unreal could not save " + asset.get_path_name())


def duplicate(source, path):
    if assets.does_asset_exist(path):
        return assets.load_asset(path)
    return assets.duplicate_asset(source, path)


def import_audio():
    for file in HERE.glob("*.wav"):
        task = u.AssetImportTask()
        task.set_editor_properties(dict(filename=str(file), destination_path=DEST, automated=True,
                                        replace_existing=True, save=True))
        tools.import_asset_tasks([task])
        if not assets.load_asset(DEST + "/" + file.stem):
            raise RuntimeError("Audio import failed for " + file.name)


def distribution(obj, name, literal):
    value = obj.get_editor_property(name)
    value.import_text(literal)
    obj.set_editor_property(name, value)


def sprite_burst(name, count, lifetime, speed, size, angle, color):
    system = duplicate("/Niagara/DefaultAssets/Templates/Systems/DirectionalBurstLightweight", DEST + "/" + name)
    emitter = system.emitter_handles[0].stateless_emitter
    initial, velocity = None, None
    for module in emitter.get_editor_property("modules"):
        kind = module.get_class().get_name().removeprefix("NiagaraStatelessModule_")
        module.set_editor_property("module_enabled", kind in ["InitializeParticle", "AddVelocity", "SolveVelocitiesAndForces"])
        if kind == "InitializeParticle":
            initial = module
        elif kind == "AddVelocity":
            velocity = module
    spawn = emitter.get_editor_property("spawn_infos")[0]
    distribution(spawn, "amount", f"(Mode=UniformConstant,Min={count},Max={count})")
    emitter.set_editor_property("spawn_infos", [spawn])
    state = emitter.get_editor_property("emitter_state")
    distribution(state, "loop_duration", "(Mode=UniformConstant,Min=.18,Max=.18,ChannelConstantsAndRanges=(.18))")
    emitter.set_editor_property("emitter_state", state)
    def span(low, high):
        return f"(Mode=UniformRange,Min={low},Max={high},ChannelConstantsAndRanges=({low},{high}))"
    distribution(initial, "lifetime_distribution", span(*lifetime))
    w0, h0, w1, h1 = size
    distribution(initial, "sprite_size_distribution",
                 f"(Mode=NonUniformRange,Min=(X={w0},Y={h0}),Max=(X={w1},Y={h1}),ChannelConstantsAndRanges=({w0},{h0},{w1},{h1}))")
    r, g, b = color
    rgba = f"(R={r},G={g},B={b},A=1)"
    distribution(initial, "color_distribution", f"(Mode=NonUniformConstant,Values=({rgba},{rgba}),ChannelConstantsAndRanges=({r},{g},{b},1))")
    distribution(velocity, "cone_velocity_distribution", span(*speed))
    velocity.set_editor_property("cone_angle", angle)
    save(system)
    return (system.get_name(), count, str(initial.get_editor_property("lifetime_distribution").get_editor_property("max")))


def prepare():
    import_audio()
    result = [
        sprite_burst("NS_CarbineMuzzle", 8, (.028, .061), (130, 320), (2.0, 4.3, 4.8, 11), 22., (45, 18, 2)),
        sprite_burst("NS_CarbineContact", 7, (.055, .172), (45, 170), (.7, 1.4, 2.1, 6.4), 66., (33, 10, 1.2)),
    ]
    body = duplicate("/Game/Variant_Shooter/Anims/ABP_TP_Rifle", ANIM + "/ABP_TempleBody")
    if not assets.does_asset_exist(ANIM + "/ABP_TempleArms"):
        factory = u.AnimBlueprintFactory()
        factory.set_editor_properties(dict(target_skeleton=u.load_asset("/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple").skeleton,
                                            parent_class=u.AnimInstance))
        arms = tools.create_asset("ABP_TempleArms", ANIM, u.AnimBlueprint, factory)
        save(arms)
    save(body)
    particle_material()
    return result


def particle_material():
    from editor import Graph, material
    graph = Graph(material("M_CarbineSpark", DEST))
    graph.m.set_editor_properties(dict(shading_model=u.MaterialShadingModel.MSM_UNLIT,
                                       blend_mode=u.BlendMode.BLEND_ADDITIVE, two_sided=True,
                                       used_with_niagara_sprites=True))
    tint = graph.node("ParticleColor")
    # Compensate for camera adaptation in the shaded jungle and in the exposed terraces.
    exposure = graph.node("EyeAdaptationInverse")
    light_value, alpha_input = u.MaterialEditingLibrary.get_material_expression_input_names(exposure)
    graph.connect(exposure, tint, str(light_value))
    graph.connect(exposure, graph.const(.85), str(alpha_input))
    graph.result(exposure, "EMISSIVE_COLOR")
    uv = graph.node("TextureCoordinate")
    centre = graph.node("Constant2Vector", r=.5, g=.5)
    radial_distance = graph.node("Distance")
    graph.connect(radial_distance, uv, "A")
    graph.connect(radial_distance, centre, "B")
    falloff = graph.node("Saturate")
    graph.connect(falloff, graph.pair("Subtract", graph.const(1.), graph.pair("Multiply", radial_distance, graph.const(2.))), "Input")
    alpha = graph.node("Multiply")
    graph.connect(alpha, falloff, "A")
    graph.connect(alpha, tint, "B", "A")
    graph.result(alpha, "OPACITY")
    mat = graph.finish()
    for name in ["NS_CarbineMuzzle", "NS_CarbineContact"]:
        system = assets.load_asset(DEST + "/" + name)
        emitter = system.emitter_handles[0].stateless_emitter
        renderer = emitter.get_editor_property("renderer_properties")[0]
        renderer.set_editor_property("material", mat)
        save(system)
    return mat.get_path_name()


def view_arms():
    """Keep the original skinned forearms, gloves, UVs and skeleton for the local camera."""
    source = "/Game/Characters/Mannequins/Meshes/SKM_Manny_Simple"
    output = duplicate(source, ANIM + "/SKM_TempleArms")
    dynamic = u.DynamicMesh()
    api, query, bones = u.GeometryScript_AssetUtils, u.GeometryScript_MeshQueries, u.GeometryScript_BoneWeights
    read = api.copy_mesh_from_skeletal_mesh(assets.load_asset(source), dynamic,
                                            u.GeometryScriptCopyMeshFromAssetOptions(), u.GeometryScriptMeshReadLOD())
    if read[1] != u.GeometryScriptOutcomePins.SUCCESS:
        raise RuntimeError("Could not read the source skeletal mesh")
    bone_info = bones.get_all_bones_info(dynamic)[1]
    arm_bones = set()
    by_name = {str(b.name): b for b in bone_info}
    upper = {}
    for side in ["l", "r"]:
        shoulder = by_name["upperarm_" + side].world_transform.translation
        elbow = by_name["lowerarm_" + side].world_transform.translation
        for bone in bone_info:
            name = str(bone.name)
            if name.startswith("upperarm") and name.endswith("_" + side):
                upper[bone.index] = (shoulder, elbow - shoulder)
    for bone in bone_info:
        if str(bone.name) in ["lowerarm_l", "lowerarm_r"] or bone.parent_index in arm_bones:
            arm_bones.add(bone.index)
    keep = []
    for vertex in range(query.get_num_vertex_i_ds(dynamic)):
        _, weight, valid = bones.get_largest_vertex_bone_weight(dynamic, vertex)
        retained = valid and weight.bone_index in arm_bones
        if valid and weight.bone_index in upper:
            shoulder, delta = upper[weight.bone_index]
            position = query.get_vertex_position(dynamic, vertex)[0]
            retained = (position - shoulder).dot(delta) > .21 * delta.dot(delta)
        keep.append(retained)
    indices = u.GeometryScript_List.convert_triangle_list_to_array(query.get_all_triangle_indices(dynamic, False)[1])
    trim = [i for i, t in enumerate(indices) if not (keep[t.x] and keep[t.y] and keep[t.z])]
    u.GeometryScript_MeshEdits.delete_triangles_from_mesh(dynamic, u.GeometryScript_List.convert_array_to_index_list(trim))
    u.GeometryScript_MeshRepair.compact_mesh(dynamic)
    source_mats = assets.load_asset(source).materials
    liner = sleeve_material()
    primitive = u.GeometryScriptPrimitiveOptions(material_id=len(source_mats))
    for side in ["l", "r"]:
        for proximal, distal, radius in [("upperarm", "lowerarm", 4.8), ("lowerarm", "hand", 3.35)]:
            joint = by_name[proximal + "_" + side]
            start = joint.world_transform.translation
            end = by_name[distal + "_" + side].world_transform.translation
            delta = end - start
            transform = u.Transform()
            transform.translation = (start + end) * .5
            transform.rotation = u.MathLibrary.make_rot_from_z(delta).quaternion()
            first_vertex = query.get_num_vertex_i_ds(dynamic)
            u.GeometryScript_Primitives.append_capsule(dynamic, primitive, transform, radius,
                                                       delta.length() - 1.3 * radius, 5, 14, 3,
                                                       u.GeometryScriptPrimitiveOriginMode.CENTER)
            weights = [u.GeometryScriptBoneWeight(bone_index=joint.index, weight=1.)]
            for vertex in range(first_vertex, query.get_num_vertex_i_ds(dynamic)):
                bones.set_vertex_bone_weights(dynamic, vertex, weights)
    subsystem = u.get_editor_subsystem(u.SkeletalMeshEditorSubsystem)
    lods = subsystem.get_lod_count(output)
    if lods > 1:
        subsystem.remove_lods(output, list(range(1, lods)))
    settings = u.GeometryScriptCopyMeshToAssetOptions()
    settings.set_editor_properties(dict(replace_materials=True,
                                        new_materials=[m.material_interface for m in source_mats] + [liner],
                                        new_material_slot_names=[m.material_slot_name for m in source_mats] + ["SleeveLining"]))
    written = api.copy_mesh_to_skeletal_mesh(dynamic, output, settings, u.GeometryScriptMeshWriteLOD())
    if written[1] != u.GeometryScriptOutcomePins.SUCCESS:
        raise RuntimeError("Could not transfer the skinned arms")
    save(output)
    return (output.get_path_name(), dynamic.get_triangle_count(), len(indices), [str(m.material_slot_name) for m in output.materials])


def sleeve_material():
    from editor import Graph, material
    graph = Graph(material("M_TempleSleeveLining", ANIM))
    u.MaterialEditingLibrary.set_material_usage(graph.m, u.MaterialUsage.MATUSAGE_SKELETAL_MESH)
    uv = graph.node("TextureCoordinate")
    waves = graph.node("Sine")
    graph.connect(waves, graph.pair("Multiply", graph.mask(uv, False, True), graph.const(100)), "Input")
    weave = graph.pair("Add", graph.const(.020), graph.pair("Multiply", waves, graph.const(.004)))
    color = graph.node("Constant3Vector", constant=u.LinearColor(.61, .67, .69, 1))
    graph.result(graph.pair("Multiply", color, weave), "BASE_COLOR")
    graph.result(graph.const(.79), "ROUGHNESS")
    return graph.finish()


def tracer():
    file = HERE / "SM_CarbineTrace.fbx"
    world = u.get_editor_subsystem(u.UnrealEditorSubsystem).get_editor_world()
    u.SystemLibrary.execute_console_command(world, "Interchange.FeatureFlags.Import.FBX 0")
    ui = u.FbxImportUI()
    ui.set_editor_properties(dict(import_mesh=True, import_materials=False, import_textures=False,
                                   import_as_skeletal=False, import_animations=False, automated_import_should_detect_type=False,
                                   mesh_type_to_import=u.FBXImportType.FBXIT_STATIC_MESH))
    ui.static_mesh_import_data.set_editor_properties(dict(combine_meshes=True, auto_generate_collision=False,
                                                           generate_lightmap_u_vs=False, convert_scene_unit=True))
    task = u.AssetImportTask()
    task.set_editor_properties(dict(filename=str(file), destination_path=DEST, automated=True, replace_existing=True,
                                    save=True, options=ui))
    tools.import_asset_tasks([task])
    from editor import Graph, material
    g = Graph(material("M_CarbineTrace", DEST))
    g.m.set_editor_property("shading_model", u.MaterialShadingModel.MSM_UNLIT)
    g.result(g.node("Constant3Vector", constant=u.LinearColor(29, 13, 2.9, 1)), "EMISSIVE_COLOR")
    mesh = assets.load_asset(DEST + "/SM_CarbineTrace")
    mesh.set_material(0, g.finish())
    save(mesh)
    return str(mesh.get_bounding_box())
