import argparse
import os
from agentos.core.loop import AgentOS
from agentos.core.state import AgentState
from agentos.tools.toolbox import Toolbox
from agentos.guardrail.engine import GuardrailEngine
from agentos.feedback.controller import FeedbackController
from agentos.security.credentials import load_api_key
from agentos.llm.real import RealLLMClient


def main():
    parser = argparse.ArgumentParser(description="AgentOS — Coding Agent Harness")
    parser.add_argument("--task", required=True, help="Task description for the agent")
    args = parser.parse_args()

    api_key = load_api_key()
    workspace = os.path.abspath(".")

    llm = RealLLMClient(api_key=api_key)
    toolbox = Toolbox(workspace=workspace)
    guardrail = GuardrailEngine(workspace=workspace)
    feedback = FeedbackController()

    agent = AgentOS(llm=llm, toolbox=toolbox, guardrail=guardrail, feedback=feedback)
    state = AgentState(task=args.task)

    try:
        agent.run(state)
    except Exception as e:
        print(f"Agent terminated: {e}")
        return 1

    print(f"Task completed. {len(state.trajectory)} steps taken.")
    return 0


if __name__ == "__main__":
    exit(main())
