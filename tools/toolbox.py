from agentos.core.action import Action
from agentos.tools.read_file import ReadFileTool
from agentos.tools.write_file import WriteFileTool
from agentos.tools.execute_test import ExecuteTestTool


class Toolbox:
    def __init__(self, workspace: str):
        self._read = ReadFileTool(workspace)
        self._write = WriteFileTool(workspace)
        self._test = ExecuteTestTool(workspace)

    def execute(self, action: Action) -> str:
        if action.type == "Read_File":
            return self._read.execute(action.params)
        elif action.type == "Write_File":
            return self._write.execute(action.params)
        elif action.type == "Execute_Test":
            result = self._test.execute(action.params)
            stderr = result['stderr'] or (result['stdout'] if result['exit_code'] != 0 else "")
            return f"exit_code={result['exit_code']}\nstdout:\n{result['stdout']}\nstderr:\n{stderr}"
        elif action.type == "Stop":
            return "STOP"
        else:
            return f"ERROR: unknown action type: {action.type}"
