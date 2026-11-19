"""Invoke project authoring operations on the running, local Unreal MCP instance."""
from pathlib import Path
import sys
import json
import time
root=Path(__file__).resolve().parent
from ue_mcp import Mcp
action=" ".join(sys.argv[1:])
payload=f"""import sys, importlib, unreal as u
sys.path.insert(0,{root.as_posix()!r})
import valley, editor
importlib.reload(valley)
importlib.reload(editor)
{action}"""
for attempt in range(45):
    client=Mcp()
    try:
        raw=client.call("editor_toolset.toolsets.python_scripting.PythonScriptingTools.execute_python",{"script":{"content":payload,"language":"Python"}})
        print(raw)
        if "Traceback" in raw or "Error in script" in raw:sys.exit(1)
        break
    except RuntimeError as error:
        if "running a slow task" not in str(error) or attempt==44:raise
    finally:
        client.close()
    time.sleep(4)
