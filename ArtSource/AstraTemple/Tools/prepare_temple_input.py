"""Create additive French keyboard bindings from the project's English movement mappings."""
import unreal as u

DEFAULT='/Game/Input/IMC_Default'
ALIASES='/Game/AstraTemple/Input/IMC_TempleAZERTY'

def rows(context):
    return list(context.get_editor_property('default_key_mappings').get_editor_property('mappings'))

def key_value(mapping):
    return mapping.key.export_text().removeprefix('(KeyName=').removesuffix(')')

def update_rows(context,items):
    group=context.get_editor_property('default_key_mappings')
    group.set_editor_property('mappings',items)
    context.set_editor_property('default_key_mappings',group)

def movement_aliases():
    library=u.EditorAssetLibrary
    duplicate=library.load_asset(ALIASES) if library.does_asset_exist(ALIASES) else library.duplicate_asset(DEFAULT,ALIASES)
    if not duplicate:raise RuntimeError('Unable to create the project input context')
    by_key={key_value(m):m for m in rows(duplicate)}
    wanted=[]
    for source,alias in [('W','Z'),('A','Q')]:
        m=by_key[alias].copy() if alias in by_key else by_key[source].copy()
        key=m.key.copy();key.import_text(alias);m.set_editor_property('key',key)
        wanted.append(m)
    update_rows(duplicate,wanted)
    if not library.save_loaded_asset(duplicate,False):raise RuntimeError('Failed to save the temple keyboard context')
    world=u.get_editor_subsystem(u.UnrealEditorSubsystem).get_editor_world()
    u.SystemLibrary.execute_console_command(world,"RELOADCONFIG EnhancedInputDeveloperSettings")
    return [(key_value(m),m.action.get_name(),[v.get_class().get_name() for v in m.modifiers if v]) for m in rows(duplicate)]
