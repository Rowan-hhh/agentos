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
        max_steps = 30  # 增加一个硬性的最大步数安全锁，防止死循环烧 token
        step_count = 0

        while step_count < max_steps:
            step_count += 1
            prompt = self._build_prompt(state)
            raw = self._llm.generate(prompt)
            
            # 1. 记录大模型说的话
            state.history.append(Message(role="assistant", content=raw))

            action = self._parse_action(raw)
            if action.type == "Stop":
                state.trajectory.append(Step(action=action, observation="STOP"))
                break
                
            # 2. 物理防复读拦截器（彻底杜绝小模型无限读同一个文件）
            if len(state.trajectory) > 0:
                last_act = state.trajectory[-1].action
                if action.type == last_act.type and action.params == last_act.params:
                    warning_msg = (
                        "SYSTEM ERROR: You just executed the exact same action with the same parameters! "
                        "DO NOT repeat. Analyze the previous observation and take a NEW action, "
                        "or output 'Stop' if you already have the answer."
                    )
                    state.history.append(Message(role="user", content=warning_msg))
                    state.trajectory.append(Step(action=action, observation="⛔ BLOCKED: Repeated Action"))
                    continue  # 必须跳过，防止重复执行工具！

            # 3. 安全护栏检查
            guard = self._guardrail.check(action)
            if guard.blocked:
                state.trajectory.append(
                    Step(action=action, observation="", guardrail_result=guard)
                )
                state.history.append(
                    Message(role="user", content=f"GUARDRAIL BLOCKED: {guard.reason}")
                )
                continue
                
            # 4. 执行工具
            obs = self._toolbox.execute(action)
            state.trajectory.append(
                Step(action=action, observation=obs, guardrail_result=guard)
            )
            
            # 5. 测试与反馈处理
            if action.type == "Execute_Test":
                m = re.search(r"exit_code=(\d+)", obs)
                if m:
                    stdout = (
                        obs.split("stdout:\n", 1)[1].split("\nstderr:\n")[0]
                        if "stdout:\n" in obs
                        else ""
                    )
                    stderr = (
                        obs.split("stderr:\n", 1)[1]
                        if "stderr:\n" in obs
                        else ""
                    )
                    should_retry = self._feedback.process(
                        state, int(m.group(1)), stdout + "\n" + stderr
                    )
                    if should_retry:
                        state.history.append(
                            Message(
                                role="user",
                                content=self._build_error_context(state),
                            )
                        )
                        continue
            
            # 6. 将工具的观察结果正确归属为 user (环境反馈)
            state.history.append(Message(role="user", content=f"Tool Observation:\n{obs}"))

    def _build_prompt(self, state: AgentState) -> str:
        prompt = (
            "You are an AI Coding Agent. You MUST respond with a valid JSON object representing your next action.\n"
            "DO NOT output any conversational text. ONLY output the JSON.\n\n"
            "Valid Action Types:\n"
            "- Read_File (params: {'path': 'string'})\n"
            "- Write_File (params: {'path': 'string', 'content': 'string'})\n"
            "- Execute_Test (params: {'command': 'string'})\n"
            "- Stop (params: {'reason': 'string'})\n\n"
            "=========================================\n"
            f"Task: {state.task}\n"
        )
        for msg in state.history:
            prompt += f"\n[{msg.role.upper()}]: {msg.content}"
            
        prompt += "\n\n[SYSTEM]: Based on the history above, what is your NEXT action?"
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
            # 强行用正则把大模型输出中的 JSON 抠出来，具备极强的容错抗干扰能力
            json_match = re.search(r"\{.*\}", raw, re.DOTALL)
            if not json_match:
                raise ValueError("No JSON block found in response")
                
            json_str = json_match.group(0)
            data = json.loads(json_str)
            
            return Action(type=data["type"], params=data.get("params", {}))
        except Exception as e:
            return Action("Stop", {"reason": f"parse failed: {str(e)} | Raw: {raw[:50]}"})