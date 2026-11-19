"""Connect to the project's Epic MCP endpoint, or a specified local editor port."""
import argparse
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


class Mcp:
    def __init__(self, image_path=None):
        port = int(os.environ.get("ASTRA_UNREAL_MCP_PORT", "8000"))
        self.endpoint = f"http://127.0.0.1:{port}/mcp"
        self.image_path = image_path
        self.session = None
        self.request_id = 0
        self.send("initialize", {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "AstraForestLocalAuthoring", "version": "1.0"},
        })
        self.send("notifications/initialized", {}, notification=True)

    def send(self, method, params, *, notification=False):
        self.request_id += 1
        payload = {"jsonrpc": "2.0", "method": method, "params": params}
        if not notification:
            payload["id"] = self.request_id
        headers = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
        if self.session:
            headers["Mcp-Session-Id"] = self.session
            headers["MCP-Protocol-Version"] = "2025-06-18"
        request = urllib.request.Request(self.endpoint, data=json.dumps(payload).encode(), headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=300) as response:
                self.session = response.headers.get("Mcp-Session-Id", self.session)
                raw = response.read().decode("utf-8-sig").strip()
        except urllib.error.HTTPError as failure:
            raise RuntimeError(f"HTTP {failure.code} {failure.read().decode()}") from failure
        if not raw:
            return
        if raw.startswith("{"):
            result = json.loads(raw)
        else:
            records = [json.loads(line[5:].strip()) for line in raw.splitlines() if line.startswith("data:")]
            result = next((record for record in records if record.get("id") == self.request_id), {})
        if "error" in result:
            raise RuntimeError(str(result["error"]))
        return result.get("result")

    def tool(self, name, **arguments):
        deadline = time.monotonic() + 300
        while True:
            result = self.send("tools/call", {"name": name, "arguments": arguments})
            rejected_before_execution = any(
                item.get("text", "").startswith("Not run: the Unreal Editor is running a slow task")
                for item in result.get("content", [])
            )
            if not rejected_before_execution or time.monotonic() >= deadline:
                break
            time.sleep(3)
        if result.get("isError"):
            raise RuntimeError(str(result["content"]))
        parts = []
        for part in result.get("content", []):
            if part.get("type") == "text":
                parts.append(part["text"])
            elif part.get("type") == "image" and self.image_path:
                self.image_path.write_bytes(base64.b64decode(part["data"], validate=True))
                parts.append(str(self.image_path.resolve()))
        return "\n".join(parts)

    def call(self, full_name, arguments=None):
        group, name = full_name.rsplit(".", 1)
        return self.tool("call_tool", toolset_name=group, tool_name=name, arguments=arguments or {})

    def close(self):
        if self.session:
            headers = {"Mcp-Session-Id": self.session, "MCP-Protocol-Version": "2025-06-18"}
            request = urllib.request.Request(self.endpoint, method="DELETE", headers=headers)
            try:
                with urllib.request.urlopen(request, timeout=8):
                    pass
            except (TimeoutError, urllib.error.URLError):
                pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    operations = parser.add_mutually_exclusive_group(required=True)
    operations.add_argument("--list", action="store_true")
    operations.add_argument("--describe", nargs="+")
    operations.add_argument("--group", nargs="+")
    operations.add_argument("--call")
    operations.add_argument("--script", type=Path)
    operations.add_argument("--code")
    operations.add_argument("--symbol")
    arguments = parser.add_mutually_exclusive_group()
    arguments.add_argument("--args", default="{}")
    arguments.add_argument("--args-file", type=Path)
    parser.add_argument("--save-image", type=Path)
    options = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    connection = Mcp(options.save_image)
    try:
        if options.list:
            print(connection.tool("list_toolsets"))
        elif options.describe:
            print(connection.tool("describe_tools", tool_names=options.describe))
        elif options.group:
            print(connection.tool("describe_toolsets", toolset_names=options.group))
        elif options.call:
            raw = options.args_file.read_text(encoding="utf-8-sig") if options.args_file else options.args
            print(connection.call(options.call, json.loads(raw)))
        elif options.symbol:
            print(connection.call("editor_toolset.toolsets.python_scripting.PythonScriptingTools.get_symbol", {"name": options.symbol}))
        else:
            code = options.script.read_text(encoding="utf-8-sig") if options.script else options.code
            print(connection.call("editor_toolset.toolsets.python_scripting.PythonScriptingTools.execute_python", {"script": {"content": code, "language": "Python"}}))
    finally:
        connection.close()
