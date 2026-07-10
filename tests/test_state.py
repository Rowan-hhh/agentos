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
