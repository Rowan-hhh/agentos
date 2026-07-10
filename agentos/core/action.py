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
