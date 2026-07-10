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
