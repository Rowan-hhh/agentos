from pathlib import Path


class ReadFileTool:
    def __init__(self, workspace: str):
        self._workspace = Path(workspace).resolve()

    def execute(self, params: dict) -> str:
        path = params["path"]
        target = (self._workspace / path).resolve()
        if not str(target).startswith(str(self._workspace)):
            return "ERROR: path escape detected"
        if not target.exists():
            return f"ERROR: file not found: {path}"
        if not target.is_file():
            return f"ERROR: not a file: {path}"
        return target.read_text(encoding="utf-8")
