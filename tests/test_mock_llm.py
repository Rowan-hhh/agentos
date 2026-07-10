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
