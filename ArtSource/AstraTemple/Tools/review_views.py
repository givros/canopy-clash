"""Capture successive saved cameras in the local editor, waiting for each complete PNG."""
import time
from pathlib import Path
import editor
import unreal as u

_active=None
def stop():
    global _active
    if _active is not None:
        u.unregister_slate_post_tick_callback(_active)
        _active=None

def series(names=None,prefix="Final"):
    global _active
    if _active:raise RuntimeError("A capture series is still running")
    if editor.levels.is_in_play_in_editor():raise RuntimeError("Stop PIE before photographing the editor world")
    names=list(names or editor.v.CAMERAS)
    path=editor.ROOT/"Review"
    state={"next":0,"waiting":None,"earliest":0}
    def tick(dt):
        if editor.levels.is_in_play_in_editor():
            stop()
            return
        name=state["waiting"]
        if name:
            f=path/(prefix+"-"+name+".png")
            if time.monotonic()<state["earliest"] or not f.exists() or f.stat().st_mtime<=state["old"]:return
            state["waiting"]=None
        if state["next"]<len(names):
            name=names[state["next"]];state["next"]+=1
            f=path/(prefix+"-"+name+".png")
            state.update(waiting=name,old=f.stat().st_mtime if f.exists() else 0,earliest=time.monotonic()+1.5)
            size=(1448,1086) if name=="Reference" else (1200,900)
            editor.capture(name,prefix+"-"+name,*size)
        else:
            global _active
            u.unregister_slate_post_tick_callback(_active)
            _active=None
            c=editor.all_named()["View_Reference"]
            u.get_editor_subsystem(u.UnrealEditorSubsystem).set_level_viewport_camera_info(c.get_actor_location(),c.get_actor_rotation())
    _active=u.register_slate_post_tick_callback(tick)
    return names
