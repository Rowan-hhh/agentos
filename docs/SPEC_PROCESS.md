# SPEC_PROCESS.md — 规约演进与冷启动验证

> 记录 `SPEC.md` 从模糊需求到精确规约的收敛过程，以及模拟冷启动暴露的设计盲区。

---

## 第一部分：头脑风暴关键迭代

在调用 `brainstorming` 技能生成 `SPEC.md` 前，项目需求只是一个模糊的念头——"用 AI 自动修 bug"。经过 4 轮问答收敛为精确的 5 阶段流水线规约。以下是最关键的两个问题及其决策影响：

### 问题 1：治理护栏的硬代码边界

**我的提问：** "您预期需要哪几条具体拦截规则？例如拦截 Write\_File 写到 Git 跟踪文件之外的路径，还是拦截 Execute\_Test 包含危险选项？"

**用户决策：**
- 路径围栏锁定在工作区（`os.path.commonpath([workspace, target]) == workspace`）
- 命令白名单仅允许 `npm test` / `pytest`，拦截 `;` `&&` `|` 等注入字符
- **所有规则必须为硬代码，非提示词控制**

**规约影响：** 这直接决定了 `guardrail/` 模块的架构——不是可插拔规则引擎，而是固化的 `rules.py` + `engine.py` 分派器。

### 问题 2：API 凭据的内存隔离机制

**我的提问：** "API Key 如何录入？.env 文件、终端输入，还是两者兼有？"

**用户决策：**
- `.env` 优先 → `getpass` 兜底
- **安全红线**：Key 绝不落盘、不入 AgentState、不入日志、不入 Traceback
- `RealLLMClient` 须重写 `__repr__` / `__str__` 防泄漏

**规约影响：** 这催生了 `security/credentials.py` 专司录入，`RealLLMClient` 内私有 `_api_key` + `__del__` 覆写的内存隔离方案。

### 其他关键收敛

| 轮次 | 模糊起点 | 精确终点 |
|------|----------|----------|
| R1 | "一些工具" | 限定 3 种：Read\_File / Write\_File / Execute\_Test |
| R2 | "随便什么上下文" | 结构化 `AgentState`：history / trajectory / currentFiles / errorLogs |
| R3 | "可以 mock" | 构造注入 + 动作队列编排，并发安全 |
| R4 | "打包发出去" | Docker + `python:3.12-slim` 多架构 |

---

## 第二部分：冷启动试运行证据（模拟复盘）

### 场景设定

假设在 SPEC 定稿后，我们将 `SPEC.md` 和 `PLAN.md` 喂给一个**纯净的 Cursor Agent**（陌生智能体，无该项目的前序对话历史），让它执行 Task 4（Toolbox + Three Tools）。

### 暴露的设计缺陷

#### 缺陷 A：`Execute_Test` 的 `shell=True` 盲区

Cursor Agent 在实现 `execute_test.py` 时，可能写出如下代码：

```python
# Cursor Agent 的初版（有漏洞）
import subprocess
result = subprocess.run(cmd, capture_output=True, text=True, shell=True)
```

**原因分析：** `SPEC.md` 第 5.2 节仅要求"受命令白名单约束"，未显式要求 `shell=False`。Cursor Agent 没有前一阶段的"安全第一"上下文，自然选择了便捷的 `shell=True`。

**后果：** 即使有命令白名单拦截 `;` `&&` `|`，`shell=True` 仍可能通过 shell 特性（环境变量展开、通配符解析）引入攻击面。例如传入 `pytest $HOME` 会在白名单下放行，但 shell 会展开 `$HOME`。

#### 缺陷 B：`Write_File` 的路径锚定歧义

Cursor Agent 在处理 `Write_File` 时，可能直接使用用户提供的路径：

```python
# Cursor Agent 的初版（有漏洞）
def execute(self, params):
    path = params["path"]  # 如 "/tmp/foo.txt"
    Path(path).write_text(params["content"])
```

**原因分析：** `SPEC.md` 第 6.2 节 G1 规则的伪代码中写了 `workspace_root` 概念，但没有显式说明路径应**始终以 workspace 为锚点进行相对路径解析**——即 `workspace / path` 而非直接使用 `path`。

**后果：** Agent 可以写任意绝对路径。虽然 Guardrail（Task 5）会拦截，但 Task 4 的工具自身没有做基本校验，违反了"纵深防御"原则——单一关卡失效即全盘失守。

### SPEC/PLAN 的修订

#### 修订 A：显式追加 `shell=False` 约束

在 `SPEC.md` 第 5.3 节补充：

```
- `Execute_Test` 使用 `subprocess.run()` 且必须设置 `shell=False`
  （禁止 shell 解释器介入，消除环境变量展开/通配符注入风险）
```

在 `PLAN.md` Task 4 的 `execute_test.py` 代码中将 `subprocess.run(shlex.split(cmd), ...)` 改为显式注释说明不经过 shell。

**实际开发中的加固效果：** Task 4 的 implementer 正确使用了 `subprocess.run(shlex.split(cmd), capture_output=True, text=True, timeout=60)`，未使用 `shell=True`。

#### 修订 B：显式锁定相对路径锚定

在 `SPEC.md` 第 6.2 节 G1 伪代码中强化表述：

```
# 修订前：
target_abs = os.path.abspath(os.path.join(workspace_root, path))

# 修订后（显式说明）：
# path 必须为相对路径，引擎始终以 workspace_root 为锚点拼接
target_abs = os.path.abspath(os.path.join(workspace_root, path))
if not target_abs.startswith(workspace_root):
    return GUARDRAIL_BLOCKED(...)
```

在 `PLAN.md` Task 4 的 `read_file.py` / `write_file.py` 代码中，路径处理统一为 `(self._workspace / path).resolve()` 模式，确保 `path` 被当作相对路径处理。

**实际开发中的加固效果：** Task 4 的 implementer 正确实现了 `target = (self._workspace / path).resolve()` + `str(target).startswith(str(self._workspace))` 双重校验。同时 Task 5 的 GuardrailEngine 又增加了一层独立检查——形成了"工具自身校验 → 护栏二次拦截"的纵深防御。

### 冷启动暴露盲区汇总

| 盲区 | 根因 | 规约加固 | 代码加固 |
|------|------|----------|----------|
| `shell=True` 风险 | SPEC 未显式写死 `shell=False` | 第 5.3 节追加约束 | `subprocess.run(shlex.split(...))` 无 shell |
| 绝对路径写入 | SPEC 未要求工具自身做锚定 | 第 6.2 节强化路径拼接说明 | `(workspace / path).resolve()` + 双重校验 |
| 单一关卡依赖 | SPEC 未体现纵深防御原则 | 无 SPEC 变更（架构决策） | Task 4 工具自检 + Task 5 护栏拦截 = 两层 |

---

## 第三部分：反思

### `brainstorming` 技能的优势

1. **强制性收敛**：如果没有逐轮问答，项目可能一直停留在"做一个 Agent 框架"的模糊层面。四轮问答强迫我们从工具选型、上下文结构、护栏机制、Mock 方案逐一决策，确保每个维度都有明确的结论而非"到时候再说"。

2. **红线显式化**：用户的三条架构红线（禁用框架、硬代码核心机制、Mock 注入）在问答前只是隐式约束，brainstorming 将其升格为 SPEC 第 2 节的显式表格——后续所有实现决策都以此为判据。

3. **预防 scope creep**：问答中用户主动限定了工具数量（3 种）和上下文结构（4 个字段），防止了后续实现中"再加一个工具"或"再塞一个字段"的膨胀倾向。

### `brainstorming` 技能的局限

1. **无法暴露实现层的盲区**：如上文的 `shell=True` 和路径锚定问题，brainstorming 在抽象层面无法发现——这些只有在冷启动试运行或实际编码时才会浮现。brainstorming 收敛的是"做什么"，不是"怎么做才不会错"。

2. **对用户领域的依赖**：如果用户没有明确说出"路径围栏"或"`__repr__` 防泄漏"，brainstorming 可能不会触及这些深水区。好在本项目的用户有明确的安全意识。

3. **接口契约的粒度有限**：brainstorming 产出的接口（如 `AgentState` 的 4 个字段）足够用于架构决策，但不够精确到方法签名。这需要 `writing-plans` 技能来落地到 `Action.to_llm_response() -> str` 级别。

### 改进建议

未来类似项目可以在 brainstorming 之后、writing-plans 之前，增加一轮**安全攻防推演**——针对每个工具接口模拟恶意输入，反向检验 SPEC 的完备性。这可能比冷启动试运行更早地捕获 `shell=True` 和路径锚定类问题。
