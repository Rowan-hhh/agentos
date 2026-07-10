# AgentOS — 开发日志

> 记录 2026-07-10 从零构建 Coding Agent Harness 的完整开发历程

---

## 开发概览

- **总用时**：约 6 小时（包含 SPEC 头脑风暴 + 8 个 TDD 任务 + CI/文档收尾）
- **总 Commits**：11 个
- **总单测**：34 PASS / 0 FAIL / 1 SKIP
- **核心工作流**：`brainstorming` → `writing-plans` → `subagent-driven-development` → `finishing-a-development-branch`

---

## 阶段 0：SPEC 头脑风暴

> 技能：`brainstorming`  
> 产出：`SPEC.md`

通过 4 轮问答确定核心架构：

1. **工具选型**：限定 3 种强管控工具（Read\_File / Write\_File / Execute\_Test）
2. **上下文结构**：结构化 `AgentState` 状态机（history / trajectory / currentFiles / errorLogs）
3. **治理护栏**：路径围栏 + 命令白名单，纯硬代码实现
4. **失败回灌**：结构化错误提取 + 连续 N 次相同报错硬中断
5. **Mock 机制**：构造注入 + 动作队列编排
6. **凭据安全**：`.env` → `getpass` 兜底，内存隔离禁泄漏
7. **分发形态**：Docker 多架构镜像

## 阶段 1：writing-plans（实现计划）

> 技能：`writing-plans`  
> 产出：`PLAN.md`

将 SPEC 拆解为 8 个 TDD 任务，每个任务包含精确的文件清单、接口契约、红/绿测试代码、commit 步骤。

---

## Task 1：Project Scaffold + Core Data Structures

> 时间：15:44  
> 技能：`subagent-driven-development` → Task 1 implementer  
> Commit：`b766ccd`  
> 测试：3/3 PASS

**成果：**
- `pyproject.toml`、包初始化文件、`agentos/core/state.py`（Message / ErrorEntry / Step / AgentState）、`agentos/core/action.py`（Action / GuardrailResult）、`agentos/llm/interface.py`（LLMClient ABC）
- `tests/test_state.py` 覆盖数据结构的默认值与序列化

**人工干预：** Review 通过后进入下一任务。

---

## Task 2：MockLLMClient

> 时间：15:50  
> 技能：`subagent-driven-development` → Task 2 implementer  
> Commit：`c597d38`  
> 测试：6/6 PASS

**成果：**
- `agentos/llm/mock.py` — 动作队列消费，耗尽自动返回 `Stop`
- 构造拷贝 `list(action_queue)` 防外部变异

**人工干预：** 发现 `__pycache__` 被误提交，amend 后追加 `.gitignore`。

---

## Task 3：RealLLMClient + Credential Security

> 时间：15:56  
> 技能：`subagent-driven-development` → Task 3 implementer  
> Commit：`91d4db3`  
> 测试：6/6 PASS + 1 SKIP

**成果：**
- `agentos/llm/real.py` — OpenAI 调用，`__repr__`/`__str__` 防泄漏，`__del__` 覆写 Key
- `agentos/security/credentials.py` — `.env` 优先 → `getpass` 兜底
- `tests/test_real_llm.py` — `@pytest.mark.skip` 脱机跳过

**人工红线：** 用户强调 API Key 内存隔离、防泄漏打印、集成测试标记跳过。

---

## Task 4：Toolbox + Three Tools

> 时间：16:03  
> 技能：`subagent-driven-development` → Task 4 implementer  
> Commit：`4527ba6`  
> 测试：15/15 PASS + 1 SKIP

**成果：**
- `agentos/tools/read_file.py` / `write_file.py` — `Path.resolve()` 路径围栏
- `agentos/tools/execute_test.py` — `shlex.split()` 提取基准程序，`subprocess.run` 无 shell，拦截 `;&|`\n`
- `agentos/tools/toolbox.py` — 按 Action 类型分派

**人工红线：** 用户强调沙箱兜底——工具自身必须实现基本路径/命令校验，不能依赖上层 GuardrailEngine 兜底。测试用例必须覆盖 `../` 逸散和 `;`/`&&` 注入。

---

## Task 5：GuardrailEngine

> 时间：16:09  
> 技能：`subagent-driven-development` → Task 5 implementer  
> Commit：`ae9c86e`  
> 测试：23/23 PASS + 1 SKIP

**成果：**
- `agentos/guardrail/rules.py` — `check_path_fence()` + `check_command_whitelist()` 纯函数
- `agentos/guardrail/engine.py` — 按 Action 类型分派，返回 `GuardrailResult`
- 8 条测试覆盖 G1/G2 全部路径

**人工红线：** 用户强调职责解耦——`GuardrailEngine` 必须独立硬代码实现，**绝对不导入** `agentos/tools/` 的任何代码。拦截理由必须清晰可测。

---

## Task 6：FeedbackController + Error Extractor

> 时间：16:20  
> 技能：`subagent-driven-development` → Task 6 implementer  
> Commit：`6f4c249`  
> 测试：29/29 PASS + 1 SKIP

**成果：**
- `agentos/feedback/extractor.py` — 纯正则提取 `{error_type, message, location}`
- `agentos/feedback/controller.py` — `process()` + `AgentLoopDeadError`
- 6 条测试覆盖成功/失败/死循环/重置/非 Traceback 输入

**人工红线：** 用户强调错误提取器必须使用纯 Python 正则，**严禁调用 LLM** 来总结或提取错误。

---

## Task 7：AgentOS Main Loop

> 时间：16:51  
> 技能：`subagent-driven-development` → Task 7 implementer  
> Commit：`20ec630`  
> 测试：34/34 PASS + 1 SKIP

**成果：**
- `agentos/core/loop.py` — 5 阶段流水线完整实现
- 每轮 Action 精确记录到 `state.trajectory`（含 Stop / 拦截 / 执行）
- Execute\_Test 失败通过 `FeedbackController` 回灌

**人工红线：**
- 用户强调轨迹记录完整性是验收核心证据——**每个 Action 必须产生一个 `Step`**
- Subagent 在实现中发现 `Execute_Test` 成功时 stdout 与 stderr 的合并问题，主动修改了 `toolbox.py` 和 `extractor.py` 处理边缘 case

---

## Task 8：CLI Entrypoint + Docker Distribution

> 时间：16:55  
> 技能：`subagent-driven-development` → Task 8 implementer  
> Commit：`e66aefc`  
> 测试：34/34 PASS + 1 SKIP

**成果：**
- `agentos/main.py` — `argparse` + `--task` + 组件装配
- `docker/Dockerfile` — `python:3.12-slim` 多架构
- `docker/entrypoint.sh` — `cd /workspace && exec agentos "$@"`

---

## 收尾阶段

> 时间：21:00–22:00

| 操作 | Commit |
|------|--------|
| GitLab CI/CD 流水线 | `6412c8b` |
| README.md 文档 | `dc704ae` |
| 本开发日志 | `AGENT_LOG.md` |
| 打包交付 | `agentos-v1.0.tar.gz` |

---

## Lessons Learned

### TDD 在 8 个任务中的护航作用

1. **接口契约先于实现**：每个 Task 的第一步都是写测试，这强制我们在写实现代码之前就明确接口签名。Task 1 的 `Action` 和 `GuardrailResult` 接口在整个项目中零修改——TDD 锁死了接触面。

2. **回归安全网**：从 Task 4 开始，每加一个新组件，都要跑全部现有测试。Task 5 修改了 `GuardrailEngine` 但 Task 4 的 9 个工具测试全部保持绿色——重构信心来自测试覆盖率，而非"小心谨慎"。

3. **红/绿节奏防止过度工程**：先看到测试失败（红），再实现到刚好通过（绿）。Task 6 的 `extract_error` 第一次实现时过度复杂（试图解析多帧 Traceback），测试驱动迫使我们精简到只提取首帧信息——刚好满足验收需求，无多余代码。

4. **Mock 注入消除外部依赖**：`MockLLMClient` 使主循环测试（Task 7）完全不依赖网络和 API Key。34 个单测中仅 1 个被跳过（集成测试），其余均可脱机确定性运行。这直接满足了 CI/CD 要求（`.gitlab-ci.yml` 中 `-k "not integration"` 一次性通过）。

5. **人工 Review 捕获了自动化测试无法覆盖的东西**：`__pycache__` 被误提交、凭据安全设计的完善程度、职责解耦的边界——这些都不是测试能验证的，但 Review 环确保了质量门禁。

> TDD 在这个项目中的核心价值不是"测试"，而是**设计约束**：它迫使我们在写代码之前先思考接口，在重构之前先确认回归，在提交之前先验证正确性。
