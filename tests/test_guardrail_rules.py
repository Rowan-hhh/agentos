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
