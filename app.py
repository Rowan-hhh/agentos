import os
import gradio as gr
from agentos.core.loop import AgentOS
from agentos.core.state import AgentState
from agentos.tools.toolbox import Toolbox
from agentos.guardrail.engine import GuardrailEngine
from agentos.feedback.controller import FeedbackController
from agentos.security.credentials import load_api_key
from agentos.llm.real import RealLLMClient


def run_agent(task: str) -> str:
    if not task.strip():
        return "Please enter a task description."

    try:
        api_key = load_api_key()
    except Exception as e:
        return f"Failed to load API key: {e}"

    workspace = os.path.abspath(".")
    try:
        llm = RealLLMClient(api_key=api_key)
        toolbox = Toolbox(workspace=workspace)
        guardrail = GuardrailEngine(workspace=workspace)
        feedback = FeedbackController()
        agent = AgentOS(llm=llm, toolbox=toolbox, guardrail=guardrail, feedback=feedback)
        state = AgentState(task=task)
        agent.run(state)
    except Exception as e:
        return f"Agent terminated with error: {e}"

    lines = [f"Task: {state.task}", f"Steps: {len(state.trajectory)}", ""]
    for i, step in enumerate(state.trajectory, 1):
        act = step.action
        lines.append(f"[{i}] {act.type} {act.params}")
        if step.guardrail_result and step.guardrail_result.blocked:
            lines.append(f"    ⛔ BLOCKED: {step.guardrail_result.reason}")
        elif step.observation:
            obs = step.observation[:200]
            lines.append(f"    → {obs}")
        lines.append("")

    if state.error_logs:
        lines.append("--- Error Logs ---")
        for err in state.error_logs:
            lines.append(f"  {err.error_type} @ {err.location}: {err.message}")

    return "\n".join(lines)


with gr.Blocks(title="AgentOS") as demo:
    gr.Markdown("# AgentOS — Coding Agent Harness")
    task_input = gr.Textbox(label="Task", placeholder="e.g. Fix the failing test in tests/")
    run_btn = gr.Button("Launch Agent", variant="primary")
    output = gr.Textbox(label="Trajectory", lines=20)
    run_btn.click(fn=run_agent, inputs=task_input, outputs=output)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    demo.launch(server_name="0.0.0.0", server_port=port)
