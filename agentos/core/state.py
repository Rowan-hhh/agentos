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
