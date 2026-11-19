"""Extract complete botanical specimens from the original, separately modeled objects."""
from pathlib import Path
import bpy
from mathutils import Matrix

root=Path(__file__).resolve().parent
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.scene.unit_settings.system='METRIC'
bpy.context.preferences.filepaths.save_version=0
families=[('fern_02',{'fern_02_b':'WoodFernFountain','fern_02_c':'WoodFernFan','fern_02_a':'WoodFernYoung'}),('potted_plant_02',{'potted_plant_02_leaves':'ElephantEar'})]
samples=[]
for asset,selection in families:
    directory=root/'Originals'/asset
    with bpy.data.libraries.load(str(directory/(asset+'_4k.blend')),link=False) as (source,loaded):
        assert set(selection)<=set(source.objects)
        loaded.objects=list(selection)
    for ob in loaded.objects:
        name=selection[ob.name]
        bpy.context.scene.collection.objects.link(ob)
        bpy.context.view_layer.update()
        transform=ob.matrix_world.copy()
        transform.translation=(0,0,0)
        ob.data.transform(transform)
        ob.matrix_world=Matrix.Identity(4)
        ob.name='SM_'+name
        ob.data.name=ob.name
        ob['source_object']=next(k for k,v in selection.items() if v==name)
        ob['source_url']='https://polyhaven.com/a/'+asset
        for mat in ob.data.materials:
            mat.name='M_'+('WoodFern' if asset=='fern_02' else 'ElephantEar')
            for node in mat.node_tree.nodes:
                if node.type=='TEX_IMAGE' and node.image:
                    image=node.image
                    src=directory/'textures'/Path(image.filepath).name
                    if not src.exists():raise FileNotFoundError(src)
                    image.filepath='//'+src.relative_to(root).as_posix()
        bpy.ops.object.select_all(action='DESELECT')
        ob.select_set(True)
        bpy.context.view_layer.objects.active=ob
        bpy.ops.export_scene.fbx(filepath=str(root/(ob.name+'.fbx')),use_selection=True,object_types={'MESH'},axis_forward='-Y',axis_up='Z',apply_unit_scale=True,apply_scale_options='FBX_SCALE_UNITS',bake_anim=False,mesh_smooth_type='FACE',path_mode='STRIP')
        samples.append(ob)
for i,ob in enumerate(samples):ob.location=(0,1.25*i,0)
bpy.ops.wm.save_as_mainfile(filepath=str(root/'UnderstorySpecimens.blend'),relative_remap=False)
