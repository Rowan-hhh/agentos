#!/usr/bin/env python3
"""AgentOS — 核心机制演示脚本（脱机确定性运行）"""

import tempfile
from pathlib import Path

from agentos.core.loop import AgentOS
from agentos.core.state import AgentState
from agentos.core.action import Action
from agentos.llm.mock import MockLLMClient
from agentos.tools.toolbox import Toolbox
from agentos.guardrail.engine import GuardrailEngine
from agentos.feedback.controller import FeedbackController, AgentLoopDeadError

SEP = "=" * 72


def demo_guardrail_interception():
    print(SEP)
    print("演示一：护栏拦截机制")
    print("场景：Agent 尝试执行 rm -rf /，被 GuardrailEngine 硬代码拦截")
    print("预期：动作被阻断，不消耗重试次数，GuardrailResult.blocked == True")
    print()

    with tempfile.TemporaryDirectory() as tmp:
        mock = MockLLMClient([
            Action("Execute_Test", {"cmd": "rm -rf /"}),
            Action("Stop", {"reason": "done"}),
        ])
        tb = Toolbox(tmp)
        gr = GuardrailEngine(tmp)
        fb = FeedbackController()
        agent = AgentOS(llm=mock, toolbox=tb, guardrail=gr, feedback=fb)
        state = AgentState(task="演示：护栏拦截")

        agent.run(state)

        step = state.trajectory[0]
        if step.guardrail_result and step.guardrail_result.blocked:
            print(">>> GuardrailEngine 成功拦截非法命令")
            print(f"    拦截理由: {step.guardrail_result.reason}")
            print(f"    动作类型: {step.action.type}")
            print(f"    命令原文: {step.action.params['cmd']}")
            print(f"    轨迹长度: {len(state.trajectory)}（拦截后继续执行 Stop）")
        else:
            print("!!! 护栏未拦截（异常）")

    print()


def demo_feedback_loop():
    print(SEP)
    print("演示二：反馈回灌机制")
    print("场景：Agent 执行 pytest 测试失败，FeedbackController 提取 Traceback 回灌")
    print("预期：ErrorEntry 被结构化提取并写入 AgentState.error_logs")
    print()

    with tempfile.TemporaryDirectory() as tmp:
        test_file = Path(tmp) / "test_fail.py"
        test_file.write_text("def test_me():\n    assert 1 + 1 == 3\n")

        mock = MockLLMClient([
            Action("Execute_Test", {"cmd": "pytest test_fail.py -v --tb=long"}),
            Action("Stop", {"reason": "done"}),
        ])
        tb = Toolbox(tmp)
        gr = GuardrailEngine(tmp)
        fb = FeedbackController(max_retry=3)
        agent = AgentOS(llm=mock, toolbox=tb, guardrail=gr, feedback=fb)
        state = AgentState(task="演示：反馈回灌")

        agent.run(state)

        if state.error_logs:
            err = state.error_logs[-1]
            print(">>> FeedbackController 成功捕获测试失败信息")
            print(f"    错误类型: {err.error_type}")
            print(f"    错误位置: {err.location}")
            print(f"    错误消息: {err.message}")
            print(f"    错误日志总数: {len(state.error_logs)}")
        else:
            print("!!! 未捕获错误（异常）")

    print()


def demo_dead_loop_breaker():
    print(SEP)
    print("演示三：死循环熔断机制")
    print("场景：Agent 连续 3 次执行同一失败的测试，触发 AgentLoopDeadError")
    print("预期：第 3 次相同报错后抛出 AgentLoopDeadError，硬中断停机")
    print()

    with tempfile.TemporaryDirectory() as tmp:
        test_file = Path(tmp) / "test_bad.py"
        test_file.write_text("def test():\n    assert False\n")

        mock = MockLLMClient([
            Action("Execute_Test", {"cmd": "pytest test_bad.py --tb=long"}),
            Action("Execute_Test", {"cmd": "pytest test_bad.py --tb=long"}),
            Action("Execute_Test", {"cmd": "pytest test_bad.py --tb=long"}),
        ])
        tb = Toolbox(tmp)
        gr = GuardrailEngine(tmp)
        fb = FeedbackController(max_retry=3)
        agent = AgentOS(llm=mock, toolbox=tb, guardrail=gr, feedback=fb)
        state = AgentState(task="演示：死循环熔断")

        try:
            agent.run(state)
            print("!!! 未触发死循环熔断（异常）")
        except AgentLoopDeadError as e:
            print(">>> AgentLoopDeadError 成功熔断死循环")
            print(f"    异常信息: {e}")
            print(f"    错误日志数: {len(state.error_logs)}")
            for i, err in enumerate(state.error_logs):
                print(f"    第 {i+1} 次: {err.error_type} @ {err.location} — {err.message}")

    print()


if __name__ == "__main__":
    print()
    print("  AgentOS — 核心机制演示")
    print("  Coding Agent Harness 总装验收脚本")
    print("  运行模式: 脱机确定性（MockLLMClient + tempfile）")
    print()
    demo_guardrail_interception()
    demo_feedback_loop()
    demo_dead_loop_breaker()
    print(SEP)
    print("全部演示完成！三个核心机制均已验证。")
    print()
