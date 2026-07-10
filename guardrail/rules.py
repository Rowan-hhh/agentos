import os
import re
import shlex


def check_path_fence(params: dict, workspace: str) -> str | None:
    path = params.get("path", "")
    if not path:
        return "path is empty"
    target = os.path.abspath(os.path.join(workspace, path))
    if os.path.commonpath([workspace, target]) != workspace:
        return f"path escape: {path} is outside workspace"
    return None


ALLOWED_BASES = {"npm", "pytest"}


def check_command_whitelist(params: dict, workspace: str) -> str | None:
    cmd = params.get("cmd", "")
    if not cmd.strip():
        return "command is empty"
    if re.search(r'[;&|`\n]', cmd):
        return "command contains injection characters"
    parts = shlex.split(cmd.strip())
    base = parts[0]
    if base not in ALLOWED_BASES:
        return f"base command '{base}' not allowed"
    if base == "npm" and (len(parts) < 2 or parts[1] != "test"):
        return "npm command must start with 'npm test'"
    return None
