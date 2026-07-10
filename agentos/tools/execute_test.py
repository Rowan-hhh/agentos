import subprocess
import shlex
from pathlib import Path

ALLOWED_BASES = {"npm", "pytest"}


class ExecuteTestTool:
    def __init__(self, workspace: str, timeout: int = 60):
        self._workspace = Path(workspace).resolve()
        self._timeout = timeout

    def _validate(self, cmd: str) -> str | None:
        if not cmd.strip():
            return "command is empty"
        if _has_injection_chars(cmd):
            return "command contains injection characters"
        parts = shlex.split(cmd.strip())
        base = parts[0]
        if base not in ALLOWED_BASES:
            return f"base command '{base}' not allowed (must be pytest or npm)"
        if base == "npm" and (len(parts) < 2 or parts[1] != "test"):
            return "npm command must start with 'npm test'"
        return None

    def execute(self, params: dict) -> dict:
        cmd = params["cmd"]
        error = self._validate(cmd)
        if error:
            return {"exit_code": -1, "stdout": "", "stderr": error}
        try:
            result = subprocess.run(
                shlex.split(cmd),
                capture_output=True,
                text=True,
                timeout=self._timeout,
                cwd=self._workspace,
            )
            return {
                "exit_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
        except subprocess.TimeoutExpired:
            return {"exit_code": -1, "stdout": "", "stderr": "TIMEOUT"}
        except FileNotFoundError:
            return {"exit_code": -1, "stdout": "", "stderr": f"command not found: {cmd}"}


def _has_injection_chars(cmd: str) -> bool:
    import re
    return bool(re.search(r'[;&|`\n]', cmd))
