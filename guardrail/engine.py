import os

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
