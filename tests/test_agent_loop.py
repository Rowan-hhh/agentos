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
