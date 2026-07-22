import os
import gradio as gr
from agentos.core.loop import AgentOS
from agentos.core.state import AgentState
from agentos.tools.toolbox import Toolbox
from agentos.guardrail.engine import GuardrailEngine
from agentos.feedback.controller import FeedbackController
from agentos.llm.real import RealLLMClient

# 🚨 取消导入原有的 load_api_key，避免云端触发 getpass 死锁
# from agentos.security.credentials import load_api_key

def run_agent(task: str) -> str:
    if not task.strip():
        return "Please enter a task description."

    # 👇 核心修改 1：安全、非阻塞地获取 API Key
    # 优先读取魔搭设置里的 LLM_API_KEY，如果没有再尝试 OPENAI_API_KEY
    api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
    
    if not api_key:
        return "❌ Agent Terminated: 未找到 API Key。请在魔搭的设置 -> 环境变量中配置 LLM_API_KEY。"

    workspace = os.path.abspath(".")
    try:
        # 因为你的 RealLLMClient 里已经硬编码了 njusehub.info 的 base_url，所以这里直接传 key 即可
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
    # 👇 核心修改 2：将 127.0.0.1 改为 0.0.0.0，打通容器的网络壁垒
    demo.launch(server_name="0.0.0.0", server_port=7860, share=False)