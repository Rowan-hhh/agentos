import json
import re

from agentos.core.state import AgentState, Step, Message
from agentos.core.action import Action
from agentos.llm.interface import LLMClient
from agentos.tools.toolbox import Toolbox
from agentos.guardrail.engine import GuardrailEngine
from agentos.feedback.controller import FeedbackController


class AgentOS:
    def __init__(
        self,
        llm: LLMClient,
        toolbox: Toolbox,
        guardrail: GuardrailEngine,
        feedback: FeedbackController,
    ):
        self._llm = llm
        self._toolbox = toolbox
        self._guardrail = guardrail
        self._feedback = feedback

    def run(self, state: AgentState) -> None:
        while True:
            prompt = self._build_prompt(state)
            raw = self._llm.generate(prompt)
            action = self._parse_action(raw)
            if action.type == "Stop":
                state.trajectory.append(Step(action=action, observation="STOP"))
                break
            guard = self._guardrail.check(action)
            if guard.blocked:
                state.trajectory.append(
                    Step(action=action, observation="", guardrail_result=guard)
                )
                state.history.append(
                    Message(role="user", content=f"GUARDRAIL: {guard.reason}")
                )
                continue
            obs = self._toolbox.execute(action)
            state.trajectory.append(
                Step(action=action, observation=obs, guardrail_result=guard)
            )
            if action.type == "Execute_Test" and "exit_code=" in obs:
                m = re.search(r"exit_code=(-?\d+)", obs)
                if m and int(m.group(1)) != 0:
                    stderr = (
                        obs.split("stderr:\n", 1)[1]
                        if "stderr:\n" in obs
                        else ""
                    )
                    should_retry = self._feedback.process(
                        state, int(m.group(1)), stderr
                    )
                    if should_retry:
                        state.history.append(
                            Message(
                                role="user",
                                content=self._build_error_context(state),
                            )
                        )
                    continue
            state.history.append(Message(role="assistant", content=obs))

    def _build_prompt(self, state: AgentState) -> str:
        prompt = f"Task: {state.task}\n"
        for msg in state.history:
            prompt += f"\n{msg.role}: {msg.content}"
        return prompt

    def _build_error_context(self, state: AgentState) -> str:
        ctx = "[System Error Context]\n"
        for err in state.error_logs:
            ctx += f"- Type: {err.error_type}\n"
            ctx += f"  Location: {err.location}\n"
            ctx += f"  Message: {err.message}\n"
        return ctx

    def _parse_action(self, raw: str) -> Action:
        try:
            data = json.loads(raw)
            return Action(type=data["type"], params=data.get("params", {}))
        except (json.JSONDecodeError, KeyError):
            return Action("Stop", {"reason": "parse failed"})
