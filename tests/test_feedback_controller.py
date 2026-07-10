from agentos.feedback.controller import FeedbackController, AgentLoopDeadError
from agentos.core.state import AgentState, ErrorEntry
from agentos.feedback.extractor import extract_error
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
    assert len(state.error_logs) == 3


def test_extract_returns_none_for_non_traceback():
    assert extract_error("just a warning") is None
    assert extract_error("") is None


def test_extract_returns_error_entry():
    stderr = (
        'File "tests/test_foo.py", line 42\n'
        "AssertionError: expected 5, got 3\n"
    )
    entry = extract_error(stderr)
    assert entry is not None
    assert entry.error_type == "AssertionError"
    assert entry.message == "expected 5, got 3"
    assert entry.location == "tests/test_foo.py:42"
