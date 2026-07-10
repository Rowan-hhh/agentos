from pathlib import Path


class WriteFileTool:
    def __init__(self, workspace: str):
        self._workspace = Path(workspace).resolve()

    def execute(self, params: dict) -> str:
        path = params["path"]
        content = params["content"]
        target = (self._workspace / path).resolve()
        if not str(target).startswith(str(self._workspace)):
            return "ERROR: path escape detected"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return f"OK: wrote {len(content)} bytes to {path}"
