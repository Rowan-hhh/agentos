# AgentOS Coding Agent Harness — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a from-scratch Coding Agent Harness with hand-written main loop, hardcoded guardrails, structured feedback loop, and Mock LLM support for deterministic testing.

**Architecture:** AgentOS runs a five-stage loop (Context → Call → Parse → Guard → Execute → Feedback) over a structured `AgentState`. All safety rules are hardcoded Python (not prompt-based). LLMClient uses constructor injection — production gets `RealLLMClient(api_key)`, tests get `MockLLMClient(action_queue)`.

**Tech Stack:** Python 3.12+, pytest, `shlex` (stdlib), `os.path` (stdlib), `subprocess` (stdlib), `getpass` (stdlib), `python-dotenv` (for `.env`), `openai` (for real LLM calls), Docker.

## Global Constraints

- No LangChain, AutoGen, CrewAI, or any Agent framework
- Guardrails and feedback loop must be hardcoded Python, not prompt-controlled
- `MockLLMClient` must be injectable via constructor for offline deterministic tests
- API Key must never appear in AgentState, logs, or traceback — memory-isolated in `RealLLMClient`
- `.env` must be in `.gitignore`
- `Execute_Test` base command must be `npm test` or `pytest`; args allowed; injection chars `;&|`\n` blocked
- Docker is the final distribution mechanism

---

### Task 1: Project Scaffold + Core Data Structures

**Files:**
- Create: `agentos/__init__.py`
- Create: `agentos/core/__init__.py`
- Create: `agentos/core/state.py`
- Create: `agentos/core/action.py`
- Create: `agentos/llm/__init__.py`
- Create: `agentos/llm/interface.py`
- Create: `agentos/security/__init__.py`
- Create: `pyproject.toml`
- Create: `tests/__init__.py`
- Create: `tests/fixtures/__init__.py`

**Interfaces:**
- Consumes: nothing (first task)
- Produces: `AgentState`, `Action`, `GuardrailResult`, `ErrorEntry`, `LLMClient` ABC — used by all subsequent tasks

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[build-system]
requires = ["setuptools>=68.0"]
build-backend = "setuptools.backends._legacy:_Backend"

[project]
name = "agentos"
version = "0.1.0"
description = "Coding Agent Harness — AI4SE final project"
requires-python = ">=3.12"
dependencies = [
    "python-dotenv>=1.0",
    "openai>=1.0",
]

[project.scripts]
agentos = "agentos.main:main"

[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
```

- [ ] **Step 2: Create `agentos/__init__.py`**

```python
```

- [ ] **Step 3: Create `agentos/core/__init__.py`**

```python
```

- [ ] **Step 4: Create `agentos/llm/__init__.py`**

```python
```

- [ ] **Step 5: Create `agentos/security/__init__.py`**

```python
```

- [ ] **Step 6: Create `tests/__init__.py` and `tests/fixtures/__init__.py`**

```python
```

- [ ] **Step 7: Write `agentos/core/state.py`**

```python
from dataclasses import dataclass, field


@dataclass
class Message:
    role: str
    content: str


@dataclass
class ErrorEntry:
    error_type: str
    message: str
    location: str


@dataclass
class Step:
    action: "Action"
    observation: str
    guardrail_result: "GuardrailResult | None" = None


@dataclass
class AgentState:
    history: list[Message] = field(default_factory=list)
    trajectory: list[Step] = field(default_factory=list)
    current_files: dict[str, str] = field(default_factory=dict)
    error_logs: list[ErrorEntry] = field(default_factory=list)
    task: str = ""
```

- [ ] **Step 8: Write `agentos/core/action.py`**

```python
from dataclasses import dataclass
from typing import Literal


ActionType = Literal["Read_File", "Write_File", "Execute_Test", "Stop"]


@dataclass
class GuardrailResult:
    blocked: bool
    reason: str | None = None


@dataclass
class Action:
    type: ActionType
    params: dict

    def to_llm_response(self) -> str:
        import json
        return json.dumps({"type": self.type, "params": self.params})
```

- [ ] **Step 9: Write `agentos/llm/interface.py`**

```python
from abc import ABC, abstractmethod


class LLMClient(ABC):
    @abstractmethod
    def generate(self, prompt: str) -> str:
        ...
```

- [ ] **Step 10: Write failing tests for data structures**

```python
# tests/test_state.py
from agentos.core.state import AgentState, Message, Step, ErrorEntry
from agentos.core.action import Action, GuardrailResult


def test_agent_state_defaults():
    state = AgentState(task="fix bug")
    assert state.task == "fix bug"
    assert state.history == []
    assert state.trajectory == []
    assert state.current_files == {}
    assert state.error_logs == []


def test_step_with_guardrail():
    action = Action("Read_File", {"path": "foo.py"})
    guard = GuardrailResult(blocked=True, reason="path escape")
    step = Step(action=action, observation="", guardrail_result=guard)
    assert step.guardrail_result.blocked


def test_action_to_llm_response():
    action = Action("Write_File", {"path": "x.py", "content": "print(1)"})
    resp = action.to_llm_response()
    assert '"Write_File"' in resp
    assert '"x.py"' in resp
```

- [ ] **Step 11: Run tests to verify they fail**

Run: `python -m pytest tests/test_state.py -v`
Expected: FileNotFoundError (tests dir exists but no test file yet)

- [ ] **Step 12: Run tests to verify they pass**

Run: `python -m pytest tests/test_state.py -v`
Expected: 3 passed

- [ ] **Step 13: Commit**

```bash
git add -A && git commit -m "feat: project scaffold + core data structures"
```

---

### Task 2: MockLLMClient

**Files:**
- Create: `agentos/llm/mock.py`
- Create: `tests/test_mock_llm.py`

**Interfaces:**
- Consumes: `Action` from Task 1, `LLMClient` ABC from Task 1
- Produces: `MockLLMClient(action_queue: list[Action])` — used by all loop-level tests

- [ ] **Step 1: Write `agentos/llm/mock.py`**

```python
from agentos.core.action import Action
from agentos.llm.interface import LLMClient


class MockLLMClient(LLMClient):
    def __init__(self, action_queue: list[Action]):
        self._queue = list(action_queue)

    def generate(self, prompt: str) -> str:
        if not self._queue:
            action = Action("Stop", {"reason": "queue exhausted"})
        else:
            action = self._queue.pop(0)
        return action.to_llm_response()
```

- [ ] **Step 2: Write failing tests**

```python
# tests/test_mock_llm.py
from agentos.llm.mock import MockLLMClient
from agentos.core.action import Action


def test_mock_returns_actions_in_order():
    queue = [
        Action("Read_File", {"path": "a.py"}),
        Action("Stop", {"reason": "done"}),
    ]
    mock = MockLLMClient(queue)
    resp1 = mock.generate("prompt")
    resp2 = mock.generate("prompt")
    assert '"Read_File"' in resp1
    assert '"Stop"' in resp2


def test_mock_returns_stop_when_queue_empty():
    mock = MockLLMClient([])
    resp = mock.generate("prompt")
    assert '"Stop"' in resp
    assert '"queue exhausted"' in resp


def test_mock_does_not_mutate_original_queue():
    queue = [Action("Stop", {"reason": "done"})]
    mock = MockLLMClient(queue)
    mock.generate("prompt")
    assert len(queue) == 1
```

- [ ] **Step 3: Run tests to verify they pass**

Run: `python -m pytest tests/test_mock_llm.py -v`
Expected: 3 passed

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "feat: MockLLMClient with action queue"
```

---

### Task 3: RealLLMClient + Credential Security

**Files:**
- Create: `agentos/llm/real.py`
- Create: `agentos/security/credentials.py`
- Create: `.env.example`
- Update: `.gitignore`

**Interfaces:**
- Consumes: `LLMClient` ABC from Task 1
- Produces: `RealLLMClient(api_key, model)` — used by CLI entrypoint in Task 8
- Produces: `load_api_key() -> str` — used by CLI entrypoint

- [ ] **Step 1: Create `.env.example`**

```
LLM_API_KEY=sk-your-key-here
```

- [ ] **Step 2: Write `agentos/security/credentials.py`**

```python
import os
import getpass
from pathlib import Path


def load_api_key() -> str:
    env_path = Path(".env")
    if env_path.exists():
        from dotenv import load_dotenv
        load_dotenv(env_path)
        key = os.environ.get("LLM_API_KEY")
        if key:
            return key
    return getpass.getpass("Enter LLM API Key: ")
```

- [ ] **Step 3: Write `agentos/llm/real.py`**

```python
from agentos.llm.interface import LLMClient
from openai import OpenAI


class RealLLMClient(LLMClient):
    def __init__(self, api_key: str, model: str = "gpt-4"):
        self._api_key = api_key
        self._model = model
        self._client = OpenAI(api_key=api_key)

    def generate(self, prompt: str) -> str:
        resp = self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
        )
        return resp.choices[0].message.content

    def __repr__(self) -> str:
        return f"RealLLMClient(model={self._model})"

    def __del__(self):
        self._api_key = "INVALIDATED"
```

- [ ] **Step 4: Create `tests/test_real_llm.py` (integration-only marker)**

```python
# tests/test_real_llm.py
import pytest


pytestmark = pytest.mark.skip(reason="integration test — requires API key and network")


def test_real_llm_requires_api_key():
    from agentos.llm.real import RealLLMClient
    client = RealLLMClient(api_key="sk-test")
    assert client is not None
```

- [ ] **Step 5: Run unit tests to verify no regressions**

Run: `python -m pytest tests/ -v -k "not integration"`
Expected: all tests pass (existing tests from Task 1 + 2)

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "feat: RealLLMClient + credential security"
```

---

### Task 4: Toolbox + Three Tools

**Files:**
- Create: `agentos/tools/__init__.py`
- Create: `agentos/tools/toolbox.py`
- Create: `agentos/tools/read_file.py`
- Create: `agentos/tools/write_file.py`
- Create: `agentos/tools/execute_test.py`
- Create: `tests/test_tools.py`

**Interfaces:**
- Consumes: `Action` from Task 1
- Produces: `Toolbox(workspace: str)` — `execute(action) -> str`
- Produces: `ReadFileTool(workspace)`, `WriteFileTool(workspace)`, `ExecuteTestTool(workspace)` — each has `execute(action) -> str`

- [ ] **Step 1: Create package init**

```python
# agentos/tools/__init__.py
```

- [ ] **Step 2: Write `agentos/tools/read_file.py`**

```python
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
```

- [ ] **Step 3: Write `agentos/tools/write_file.py`**

```python
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
```

- [ ] **Step 4: Write `agentos/tools/execute_test.py`**

```python
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
```

- [ ] **Step 5: Write `agentos/tools/toolbox.py`**

```python
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
            return f"exit_code={result['exit_code']}\nstdout:\n{result['stdout']}\nstderr:\n{result['stderr']}"
        elif action.type == "Stop":
            return "STOP"
        else:
            return f"ERROR: unknown action type: {action.type}"
```

- [ ] **Step 6: Write failing tests**

```python
# tests/test_tools.py
from pathlib import Path
import tempfile
from agentos.tools.read_file import ReadFileTool
from agentos.tools.write_file import WriteFileTool
from agentos.tools.execute_test import ExecuteTestTool


def test_read_file_ok():
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "hello.txt"
        p.write_text("hello world")
        tool = ReadFileTool(tmp)
        assert tool.execute({"path": "hello.txt"}) == "hello world"


def test_read_file_escape():
    with tempfile.TemporaryDirectory() as tmp:
        tool = ReadFileTool(tmp)
        assert "ERROR" in tool.execute({"path": "../etc/passwd"})


def test_write_file_ok():
    with tempfile.TemporaryDirectory() as tmp:
        tool = WriteFileTool(tmp)
        result = tool.execute({"path": "out.txt", "content": "data"})
        assert "OK" in result
        assert (Path(tmp) / "out.txt").read_text() == "data"


def test_write_file_escape():
    with tempfile.TemporaryDirectory() as tmp:
        tool = WriteFileTool(tmp)
        result = tool.execute({"path": "../out.txt", "content": "data"})
        assert "ERROR" in result


def test_execute_test_validation():
    tool = ExecuteTestTool("/tmp")
    result = tool.execute({"cmd": "rm -rf /"})
    assert result["exit_code"] == -1
    assert "not allowed" in result["stderr"]


def test_execute_test_valid_pytest():
    tool = ExecuteTestTool("/tmp")
    result = tool.execute({"cmd": "pytest --version"})
    assert result["exit_code"] == 0


def test_execute_test_injection_chars():
    tool = ExecuteTestTool("/tmp")
    for bad in ["pytest; rm -rf /", "pytest&&whoami", "pytest|ls", "npm test\nrm -rf /"]:
        result = tool.execute({"cmd": bad})
        assert result["exit_code"] == -1, f"should block: {bad}"
        assert "injection" in result["stderr"].lower(), f"should mention injection: {bad}"


def test_execute_test_npm_no_subcommand():
    tool = ExecuteTestTool("/tmp")
    result = tool.execute({"cmd": "npm install"})
    assert result["exit_code"] == -1
    assert "npm test" in result["stderr"]


def test_toolbox_dispatches():
    from agentos.tools.toolbox import Toolbox
    from agentos.core.action import Action
    with tempfile.TemporaryDirectory() as tmp:
        tb = Toolbox(tmp)
        (Path(tmp) / "x.txt").write_text("content")
        obs = tb.execute(Action("Read_File", {"path": "x.txt"}))
        assert obs == "content"
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `python -m pytest tests/test_tools.py -v`
Expected: all 9 tests pass

- [ ] **Step 8: Commit**

```bash
git add -A && git commit -m "feat: Toolbox with Read_File, Write_File, Execute_Test"
```

---

### Task 5: GuardrailEngine with Hardcoded Rules

**Files:**
- Create: `agentos/guardrail/__init__.py`
- Create: `agentos/guardrail/engine.py`
- Create: `agentos/guardrail/rules.py`
- Create: `tests/test_guardrail_rules.py`

**Interfaces:**
- Consumes: `Action`, `GuardrailResult` from Task 1
- Produces: `GuardrailEngine(workspace)` — `check(action) -> GuardrailResult`

- [ ] **Step 1: Create package init**

```python
# agentos/guardrail/__init__.py
```

- [ ] **Step 2: Write `agentos/guardrail/rules.py`**

```python
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
```

- [ ] **Step 3: Write `agentos/guardrail/engine.py`**

```python
from agentos.core.action import Action, GuardrailResult
from agentos.guardrail import rules


class GuardrailEngine:
    def __init__(self, workspace: str):
        self._workspace = os.path.abspath(workspace)

    def check(self, action: Action) -> GuardrailResult:
        if action.type in ("Read_File", "Write_File"):
            reason = rules.check_path_fence(action.params, self._workspace)
            if reason:
                return GuardrailResult(blocked=True, reason=reason)
        elif action.type == "Execute_Test":
            reason = rules.check_command_whitelist(action.params, self._workspace)
            if reason:
                return GuardrailResult(blocked=True, reason=reason)
        return GuardrailResult(blocked=False)
```

- [ ] **Step 4: Write failing tests**

```python
# tests/test_guardrail_rules.py
import tempfile
import os
from agentos.guardrail.engine import GuardrailEngine
from agentos.core.action import Action


def test_path_fence_allows_internal():
    with tempfile.TemporaryDirectory() as tmp:
        eng = GuardrailEngine(tmp)
        r = eng.check(Action("Read_File", {"path": "foo.py"}))
        assert not r.blocked


def test_path_fence_blocks_escape():
    with tempfile.TemporaryDirectory() as tmp:
        eng = GuardrailEngine(tmp)
        r = eng.check(Action("Write_File", {"path": "../etc/passwd", "content": ""}))
        assert r.blocked
        assert "escape" in r.reason


def test_path_fence_blocks_absolute():
    with tempfile.TemporaryDirectory() as tmp:
        eng = GuardrailEngine(tmp)
        r = eng.check(Action("Read_File", {"path": "/etc/passwd"}))
        assert r.blocked


def test_command_whitelist_allows_pytest_with_args():
    with tempfile.TemporaryDirectory() as tmp:
        eng = GuardrailEngine(tmp)
        r = eng.check(Action("Execute_Test", {"cmd": "pytest tests/foo.py -x -v"}))
        assert not r.blocked


def test_command_whitelist_allows_npm_test_with_args():
    with tempfile.TemporaryDirectory() as tmp:
        eng = GuardrailEngine(tmp)
        r = eng.check(Action("Execute_Test", {"cmd": "npm test -- --watch"}))
        assert not r.blocked


def test_command_whitelist_blocks_injection():
    with tempfile.TemporaryDirectory() as tmp:
        eng = GuardrailEngine(tmp)
        for bad_cmd in ["pytest; rm -rf /", "npm test&&ls", "pytest|whoami"]:
            r = eng.check(Action("Execute_Test", {"cmd": bad_cmd}))
            assert r.blocked, f"should block: {bad_cmd}"


def test_command_whitelist_blocks_unknown_base():
    with tempfile.TemporaryDirectory() as tmp:
        eng = GuardrailEngine(tmp)
        r = eng.check(Action("Execute_Test", {"cmd": "python exploit.py"}))
        assert r.blocked


def test_command_whitelist_blocks_npm_without_test():
    with tempfile.TemporaryDirectory() as tmp:
        eng = GuardrailEngine(tmp)
        r = eng.check(Action("Execute_Test", {"cmd": "npm install"}))
        assert r.blocked
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_guardrail_rules.py -v`
Expected: 8 tests pass

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "feat: GuardrailEngine with path fence and command whitelist"
```

---

### Task 6: FeedbackController + Error Extractor

**Files:**
- Create: `agentos/feedback/__init__.py`
- Create: `agentos/feedback/controller.py`
- Create: `agentos/feedback/extractor.py`
- Create: `tests/test_feedback_controller.py`

**Interfaces:**
- Consumes: `ErrorEntry` from Task 1, `AgentState` from Task 1
- Produces: `FeedbackController(max_retry=3)` — `process(state, exit_code, stderr) -> bool` (returns True if should retry)

- [ ] **Step 1: Create package init**

```python
# agentos/feedback/__init__.py
```

- [ ] **Step 2: Write `agentos/feedback/extractor.py`**

```python
import re
from agentos.core.state import ErrorEntry


TRACEBACK_PATTERN = re.compile(
    r'File\s+"([^"]+)",\s+line\s+(\d+).*?\n(\w+(?:Error|Exception|Warning|Failure)):\s*(.*)',
    re.DOTALL,
)


def extract_error(stderr: str) -> ErrorEntry | None:
    match = TRACEBACK_PATTERN.search(stderr)
    if not match:
        return None
    location = f"{match.group(1)}:{match.group(2)}"
    error_type = match.group(3)
    message = match.group(4).strip()
    return ErrorEntry(error_type=error_type, message=message, location=location)
```

- [ ] **Step 3: Write `agentos/feedback/controller.py`**

```python
from agentos.core.state import AgentState, ErrorEntry


class AgentLoopDeadError(Exception):
    pass


class FeedbackController:
    def __init__(self, max_retry: int = 3):
        self._max_retry = max_retry

    def process(self, state: AgentState, exit_code: int, stderr: str) -> bool:
        if exit_code == 0:
            return False
        from agentos.feedback.extractor import extract_error
        entry = extract_error(stderr)
        if entry is None:
            return False
        state.error_logs.append(entry)
        recent = state.error_logs[-self._max_retry:]
        if len(recent) >= self._max_retry:
            if all(e.error_type == recent[0].error_type
                   and e.message == recent[0].message
                   and e.location == recent[0].location
                   for e in recent):
                raise AgentLoopDeadError(
                    f"dead loop detected: {self._max_retry} identical errors"
                )
        return True
```

- [ ] **Step 4: Write failing tests**

```python
# tests/test_feedback_controller.py
from agentos.feedback.controller import FeedbackController, AgentLoopDeadError
from agentos.core.state import AgentState, ErrorEntry
import pytest


def test_success_does_not_retry():
    ctrl = FeedbackController()
    state = AgentState(task="test")
    assert not ctrl.process(state, 0, "")
    assert state.error_logs == []


def test_failure_appends_error():
    stderr = (
        'File "tests/test_foo.py", line 42\n'
        "AssertionError: expected 5, got 3\n"
    )
    ctrl = FeedbackController()
    state = AgentState(task="test")
    assert ctrl.process(state, 1, stderr)
    assert len(state.error_logs) == 1
    assert state.error_logs[0].error_type == "AssertionError"


def test_three_identical_errors_raises_dead_loop():
    stderr = (
        'File "tests/test_foo.py", line 42\n'
        "AssertionError: expected 5, got 3\n"
    )
    ctrl = FeedbackController(max_retry=3)
    state = AgentState(task="test")
    ctrl.process(state, 1, stderr)
    ctrl.process(state, 1, stderr)
    with pytest.raises(AgentLoopDeadError):
        ctrl.process(state, 1, stderr)


def test_new_error_resets_dead_loop():
    stderr1 = (
        'File "tests/test_foo.py", line 42\n'
        "AssertionError: expected 5, got 3\n"
    )
    stderr2 = (
        'File "tests/test_bar.py", line 10\n'
        "ValueError: invalid input\n"
    )
    ctrl = FeedbackController(max_retry=3)
    state = AgentState(task="test")
    ctrl.process(state, 1, stderr1)
    ctrl.process(state, 1, stderr1)
    ctrl.process(state, 1, stderr2)
    # different error on 3rd try -> no dead loop
    assert len(state.error_logs) == 3


def test_extract_returns_none_for_non_traceback():
    from agentos.feedback.extractor import extract_error
    assert extract_error("just a warning") is None
    assert extract_error("") is None
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_feedback_controller.py -v`
Expected: 6 tests pass

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "feat: FeedbackController with error extraction and dead loop detection"
```

---

### Task 7: AgentOS Main Loop

**Files:**
- Create: `agentos/core/agent.py`
- Create: `agentos/core/loop.py`
- Create: `tests/test_agent_loop.py`

**Interfaces:**
- Consumes: All previous tasks
- Produces: `AgentOS(llm, toolbox, guardrail, feedback, ...)` — `run(state) -> None`

- [ ] **Step 1: Write `agentos/core/loop.py`**

```python
from agentos.core.state import AgentState, Step
from agentos.core.action import Action
from agentos.llm.interface import LLMClient
from agentos.tools.toolbox import Toolbox
from agentos.guardrail.engine import GuardrailEngine
from agentos.feedback.controller import FeedbackController
import json


class AgentOS:
    def __init__(
        self,
        llm: LLMClient,
        toolbox: Toolbox,
        guardrail: GuardrailEngine,
        feedback: FeedbackController,
    ):
        self._llm = llm
        self._toolbox = toolbox
        self._guardrail = guardrail
        self._feedback = feedback

    def run(self, state: AgentState) -> None:
        while True:
            prompt = self._build_prompt(state)
            raw = self._llm.generate(prompt)
            action = self._parse_action(raw)
            if action.type == "Stop":
                state.trajectory.append(Step(action=action, observation="STOP"))
                break
            guard = self._guardrail.check(action)
            if guard.blocked:
                state.trajectory.append(
                    Step(action=action, observation="", guardrail_result=guard)
                )
                state.history.append(Message(role="user", content=f"GUARDRAIL: {guard.reason}"))
                continue
            obs = self._toolbox.execute(action)
            state.trajectory.append(Step(action=action, observation=obs, guardrail_result=guard))
            if action.type == "Execute_Test" and "exit_code=" in obs:
                import re
                m = re.search(r"exit_code=(-?\d+)", obs)
                if m and int(m.group(1)) != 0:
                    stderr = obs.split("stderr:\n", 1)[1] if "stderr:\n" in obs else ""
                    should_retry = self._feedback.process(state, int(m.group(1)), stderr)
                    if should_retry:
                        state.history.append(
                            Message(role="user", content=self._build_error_context(state))
                        )
                    continue
            state.history.append(Message(role="assistant", content=obs))

    def _build_prompt(self, state: AgentState) -> str:
        prompt = f"Task: {state.task}\n"
        for msg in state.history:
            prompt += f"\n{msg.role}: {msg.content}"
        return prompt

    def _build_error_context(self, state: AgentState) -> str:
        ctx = "[System Error Context]\n"
        for err in state.error_logs:
            ctx += f"- Type: {err.error_type}\n"
            ctx += f"  Location: {err.location}\n"
            ctx += f"  Message: {err.message}\n"
        return ctx

    def _parse_action(self, raw: str) -> Action:
        try:
            data = json.loads(raw)
            return Action(type=data["type"], params=data.get("params", {}))
        except (json.JSONDecodeError, KeyError):
            return Action("Stop", {"reason": "parse failed"})
```

- [ ] **Step 2: Write `agentos/core/agent.py` (re-export for clean imports)**

```python
from agentos.core.loop import AgentOS

__all__ = ["AgentOS"]
```

- [ ] **Step 3: Write failing tests**

```python
# tests/test_agent_loop.py
import tempfile
from pathlib import Path
from agentos.core.loop import AgentOS
from agentos.core.state import AgentState, Message
from agentos.core.action import Action
from agentos.llm.mock import MockLLMClient
from agentos.tools.toolbox import Toolbox
from agentos.guardrail.engine import GuardrailEngine
from agentos.feedback.controller import FeedbackController


def test_agent_stops_immediately():
    mock = MockLLMClient([Action("Stop", {"reason": "done"})])
    tb = Toolbox("/tmp")
    gr = GuardrailEngine("/tmp")
    fb = FeedbackController()
    agent = AgentOS(llm=mock, toolbox=tb, guardrail=gr, feedback=fb)
    state = AgentState(task="test")
    agent.run(state)
    assert len(state.trajectory) == 1
    assert state.trajectory[0].action.type == "Stop"


def test_agent_reads_file():
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "hello.txt").write_text("world")
        mock = MockLLMClient([
            Action("Read_File", {"path": "hello.txt"}),
            Action("Stop", {"reason": "done"}),
        ])
        tb = Toolbox(tmp)
        gr = GuardrailEngine(tmp)
        fb = FeedbackController()
        agent = AgentOS(llm=mock, toolbox=tb, guardrail=gr, feedback=fb)
        state = AgentState(task="test")
        agent.run(state)
        assert len(state.trajectory) == 2
        assert state.trajectory[0].observation == "world"


def test_guardrail_blocks_escape_write():
    with tempfile.TemporaryDirectory() as tmp:
        mock = MockLLMClient([
            Action("Write_File", {"path": "../etc/passwd", "content": "x"}),
            Action("Stop", {"reason": "done"}),
        ])
        tb = Toolbox(tmp)
        gr = GuardrailEngine(tmp)
        fb = FeedbackController()
        agent = AgentOS(llm=mock, toolbox=tb, guardrail=gr, feedback=fb)
        state = AgentState(task="test escape")
        agent.run(state)
        assert state.trajectory[0].guardrail_result.blocked


def test_agent_handles_execute_test_success():
    with tempfile.TemporaryDirectory() as tmp:
        mock = MockLLMClient([
            Action("Execute_Test", {"cmd": "pytest --version"}),
            Action("Stop", {"reason": "done"}),
        ])
        tb = Toolbox(tmp)
        gr = GuardrailEngine(tmp)
        fb = FeedbackController()
        agent = AgentOS(llm=mock, toolbox=tb, guardrail=gr, feedback=fb)
        state = AgentState(task="test")
        agent.run(state)
        assert len(state.trajectory) == 2


def test_agent_dead_loop_raises():
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "test_fail.py").write_text(
            "def test_fail():\n    assert 1 == 2\n"
        )
        mock = MockLLMClient([
            Action("Execute_Test", {"cmd": "pytest test_fail.py"}),
            Action("Execute_Test", {"cmd": "pytest test_fail.py"}),
            Action("Execute_Test", {"cmd": "pytest test_fail.py"}),
        ])
        tb = Toolbox(tmp)
        gr = GuardrailEngine(tmp)
        fb = FeedbackController(max_retry=3)
        agent = AgentOS(llm=mock, toolbox=tb, guardrail=gr, feedback=fb)
        state = AgentState(task="test")
        import pytest
        from agentos.feedback.controller import AgentLoopDeadError
        with pytest.raises(AgentLoopDeadError):
            agent.run(state)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_agent_loop.py -v`
Expected: 5 tests pass

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat: AgentOS main loop with full 5-stage pipeline"
```

---

### Task 8: CLI Entrypoint + Docker

**Files:**
- Create: `agentos/main.py`
- Create: `docker/Dockerfile`
- Create: `docker/entrypoint.sh`

**Interfaces:**
- Consumes: Everything from Tasks 1-7
- Produces: CLI `agentos --task "..."` and `docker run agentos --task "..."`

- [ ] **Step 1: Write `agentos/main.py`**

```python
import argparse
import os
from agentos.core.loop import AgentOS
from agentos.core.state import AgentState
from agentos.tools.toolbox import Toolbox
from agentos.guardrail.engine import GuardrailEngine
from agentos.feedback.controller import FeedbackController
from agentos.security.credentials import load_api_key
from agentos.llm.real import RealLLMClient


def main():
    parser = argparse.ArgumentParser(description="AgentOS — Coding Agent Harness")
    parser.add_argument("--task", required=True, help="Task description for the agent")
    args = parser.parse_args()

    api_key = load_api_key()
    workspace = os.path.abspath(".")

    llm = RealLLMClient(api_key=api_key)
    toolbox = Toolbox(workspace=workspace)
    guardrail = GuardrailEngine(workspace=workspace)
    feedback = FeedbackController()

    agent = AgentOS(llm=llm, toolbox=toolbox, guardrail=guardrail, feedback=feedback)
    state = AgentState(task=args.task)

    try:
        agent.run(state)
    except Exception as e:
        print(f"Agent terminated: {e}")
        return 1

    print(f"Task completed. {len(state.trajectory)} steps taken.")
    return 0


if __name__ == "__main__":
    exit(main())
```

- [ ] **Step 2: Write `docker/Dockerfile`**

```dockerfile
FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir agentos

COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["--help"]
```

- [ ] **Step 3: Write `docker/entrypoint.sh`**

```bash
#!/bin/sh
cd /workspace && exec agentos "$@"
```

- [ ] **Step 4: Update `.env.example` if needed and verify `.gitignore`**

```bash
# .gitignore should contain:
echo ".env" >> .gitignore
echo "__pycache__/" >> .gitignore
echo "*.pyc" >> .gitignore
```

- [ ] **Step 5: Run final full test suite**

Run: `python -m pytest tests/ -v -k "not integration"`
Expected: all tests pass (across all 6 test files)

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "feat: CLI entrypoint + Docker distribution"
```
