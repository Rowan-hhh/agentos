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
