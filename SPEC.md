# AgentOS — Coding Agent Harness 规约文档

> AI4SE 期末大作业 · 项目 A
> 版本: 1.0 · 状态: 定稿

---

## 1. 项目概述

### 1.1 目标

构建一个从零手写的 **Coding Agent 主循环基础设施**（Harness），支持：

- 接收自然语言编程任务（如"修复这个 bug"）
- 自主调用受控工具（读文件、写文件、运行测试）
- 在硬代码护栏下安全执行，防止逸散破坏
- 失败时自动结构化回灌错误信息，驱动 LLM 自我修正
- 达到死循环上限时硬中断并报错停机

### 1.2 适用范围

本规约覆盖 Agent 主循环架构、数据结构、工具系统、治理护栏、反馈闭环、Mock LLM 接口、凭据安全与部署形态。**不覆盖** LLM 模型选型、Prompt 工程策略、具体测试用例内容。

### 1.3 非目标

- 非 LangChain / AutoGen 等框架的二次封装
- 非通用 Shell 执行环境
- 非分布式多 Agent 编排

---

## 2. 架构红线（绝对不可违反）

| # | 红线 | 说明 |
|---|------|------|
| R1 | **禁用 Agent 框架** | 严禁使用 LangChain、AutoGen、CrewAI 等任何 Agent 框架。主循环必须从零手写 |
| R2 | **核心机制硬编码** | 治理护栏（路径拦截、命令白名单）和失败回灌（死循环检测）必须用 Python 硬代码实现，不得依赖 Prompt 提示词控制 |
| R3 | **强制 Mock 注入** | 系统必须通过构造注入支持 `MockLLMClient`，能够在完全脱机、无网络、无 API Key 的条件下运行确定性单元测试 |
| R4 | **凭据内存隔离** | API Key 仅在 `RealLLMClient` 实例的局部内存中存活，绝不落盘、不序列化、不入日志或 Traceback |

---

## 3. 系统架构

### 3.1 Agent 主循环（`AgentOS.run()`）

主循环是系统的唯一核心调度器，严格按以下五阶段循环执行，直到 `Stop` 动作或达到重试上限：

```
┌─────────────────────────────────────────────────────────┐
│  ① Context   →  ② Call   →  ③ Parse   →  ④ Guard   →  ⑤ Execute   │
│      ↑                                                   │
│      └──────────── ⑥ Feedback (若 Execute 失败) ──────────┘
└─────────────────────────────────────────────────────────┘
```

各阶段职责：

| 阶段 | 名称 | 职责 |
|------|------|------|
| ① | **Context Assembly** | 将 `AgentState` 序列化为发送给 LLM 的 Prompt 结构 |
| ② | **LLM Call** | 调用 `LLMClient.generate(prompt)` 获取响应文本 |
| ③ | **Response Parse** | 解析 LLM 响应，提取为结构化 `Action` 对象 |
| ④ | **Guardrail Check** | 对 `Action` 执行硬代码规则校验；若拦截则跳过 Execute，直接构造拦截反馈 |
| ⑤ | **Tool Execute** | 在 `Toolbox` 中执行合法 `Action`，返回 `Observation` |
| ⑥ | **Feedback Loop** | 若 Execute 失败（非零退出），结构化提取错误信息写入 `AgentState.errorLogs`，触发下一轮重试 |

### 3.2 组件依赖关系

```
AgentOS
  ├── LLMClient (interface, 构造注入)
  │     ├── RealLLMClient     ← api_key (内存隔离)
  │     └── MockLLMClient     ← action_queue (单测)
  ├── Toolbox
  │     ├── Read_File
  │     ├── Write_File
  │     └── Execute_Test
  ├── GuardrailEngine         ← 纯硬代码规则
  ├── FeedbackController      ← 重试计数 + 死循环检测
  └── AgentState              ← 结构化上下文（传递用，不序列化 API Key）
```

---

## 4. AgentState — 结构化上下文

### 4.1 数据定义

```python
@dataclass
class Message:
    role: str          # "user" | "assistant" | "system"
    content: str

@dataclass
class Step:
    action: Action
    observation: str
    guardrail_result: GuardrailResult | None

@dataclass
class ErrorEntry:
    error_type: str    # e.g. "AssertionError", "SyntaxError"
    message: str       # 核心错误消息
    location: str      # 文件:行号

@dataclass
class AgentState:
    history: list[Message]
    trajectory: list[Step]
    current_files: dict[str, str]   # path → content 快照
    error_logs: list[ErrorEntry]    # 仅来自 Execute_Test 失败的结构化提取
    task: str                       # 当前任务描述
```

### 4.2 设计要求

- `AgentState` 是纯数据容器，**不含** API Key 等敏感信息
- `trajectory` 保留完整执行因果链，支持 Mock 测试直接断言主循环决策
- `error_logs` 在每轮 Prompt 组装时被封装为独立的 `[System Error Context]` 节点注入

---

## 5. 工具系统（Toolbox）

### 5.1 Action 定义（LLM 输出的结构化产物）

```python
@dataclass
class Action:
    type: Literal["Read_File", "Write_File", "Execute_Test", "Stop"]
    params: dict
```

### 5.2 工具清单

| 工具 | 参数签名 | 返回值 | 说明 |
|------|----------|--------|------|
| `Read_File` | `(path: str) → str` | 文件内容 | 受路径围栏约束 |
| `Write_File` | `(path: str, content: str) → str` | 成功确认 | 受路径围栏约束，用作护栏拦截测试触发点 |
| `Execute_Test` | `(cmd: str) → dict` | `{exit_code, stdout, stderr}` | 受命令白名单约束；允许携带参数/子路径（如 `pytest tests/foo.py`），但基准程序必须为 `npm test` 或 `pytest` |
| `Stop` | `(reason: str)` | 中断循环 | 无护栏约束；Agent 自判任务完成时调用 |

### 5.3 工具安全约束

- **所有文件操作** 的工作目录锁定为项目根目录，不得通过 `../` 或绝对路径逸散
- `Execute_Test` 执行时设置超时（默认 60s），防止测试死循环拖垮宿主机
- 工具执行结果以字符串形式返回，作为 `Observation` 写入 `trajectory`

---

## 6. 治理护栏（GuardrailEngine）

### 6.1 设计原则

所有拦截规则为**纯 Python 硬代码**，不允许通过 Prompt 或配置文件注入规则逻辑。

### 6.2 规则定义

#### 规则 G1：路径围栏（作用于 `Write_File` 和 `Read_File`）

```
输入: action.params.path, workspace_root

逻辑:
  target_abs = os.path.abspath(os.path.join(workspace_root, path))
  if os.path.commonpath([workspace_root, target_abs]) != workspace_root:
      return GUARDRAIL_BLOCKED("路径逸散: 目标路径不在工作区内")
  return GUARDRAIL_PASS
```

- 适用于 `Read_File` 和 `Write_File`
- 禁止访问 `/etc/`, `/sys/`, `~/.ssh/` 等系统敏感目录
- 禁止软链接逃逸

#### 规则 G2：命令白名单（作用于 `Execute_Test`）

```
输入: action.params.cmd

逻辑:
  # 第一步：拦截注入字符（多命令串联）
  if re.search(r'[;&|`\n]', cmd):
      return GUARDRAIL_BLOCKED("命令包含注入字符（; & | ` \\n），已拦截")

  # 第二步：提取基准程序（首个单词）
  base = shlex.split(cmd.strip())[0] if cmd.strip() else ""

  # 第三步：校验基准程序必须为白名单程序
  if base not in {"npm", "pytest"}:
      return GUARDRAIL_BLOCKED(f"基准程序非法: '{base}'，仅允许 npm test 或 pytest")

  # 第四步：若基准程序为 npm，则后续首个参数必须为 test
  if base == "npm":
      args = shlex.split(cmd.strip())
      if len(args) < 2 or args[1] != "test":
          return GUARDRAIL_BLOCKED("npm 命令必须以 'npm test' 开头")

  return GUARDRAIL_PASS
```

- 拒绝任何含 `;` `&&` `||` `` ` `` `\n` 的复合命令或注入尝试
- 允许基准程序携带合法参数（如 `pytest tests/test_foo.py -x -v` 或 `npm test -- --watch`）
- 已排除 `$()` 拦截（属于 shell 解释器特性，工具使用 `subprocess.run` 不经过 shell，不存在注入风险）

### 6.3 GuardrailResult 结构

```python
@dataclass
class GuardrailResult:
    blocked: bool
    reason: str | None   # 仅 blocked=True 时有值
```

### 6.4 拦截后的控制流

```
GuardrailResult.blocked == True →
  1. 跳过 Toolbox.execute()
  2. 将 {blocked=True, reason} 写入 trajectory
  3. 构造拦截反馈消息注入下一轮 history
  4. 不消耗重试计数（护栏拦截 ≠ 执行失败）
```

---

## 7. 失败回灌（FeedbackController）

### 7.1 触发条件

`Execute_Test` 返回 `exit_code != 0` 且 `stderr` 中包含 Python Traceback / 测试失败报告。

### 7.2 结构化提取流程

```
原始 stderr → [错误提取器] → ErrorEntry{error_type, message, location}

提取规则:
  - error_type:  从 Traceback 末行提取异常类名 (如 AssertionError)
  - message:     异常消息文本
  - location:    从 Traceback 首帧提取 File "xxx.py", line N
```

提取结果写入 `AgentState.error_logs`。

### 7.3 死循环检测与硬中断

```
每轮 Execute_Test 失败后:

  if retry_count >= MAX_RETRY (N=3):
      if all 最近 N 次的 ErrorEntry 完全相同 (error_type + message + location 全部一致):
          raise AgentLoopDeadError(f"死循环检测: 连续 {N} 次相同错误，强行中断")
      else:
          # 新异类错误，重置连续相同计数
          继续重试

  retry_count += 1
```

- `MAX_RETRY = 3`（可通过构造函数参数覆盖）
- 死循环判定条件：**连续 N 次的 ErrorEntry 三元组相等**
- 硬中断以异常形式抛出，由上层调用者捕获处理

### 7.4 Prompt 注入格式

在下一轮 Context Assembly 阶段，将 `error_logs` 组装为独立消息块：

```
[System Error Context]
以下是执行测试时捕获的错误，请修正后重试：

- 类型: AssertionError
- 位置: tests/test_foo.py:42
- 消息: expected 5, got 3
```

---

## 8. LLMClient 接口与 Mock 机制

### 8.1 统一接口

```python
class LLMClient(ABC):
    @abstractmethod
    def generate(self, prompt: str) -> str:
        ...
```

### 8.2 RealLLMClient

```python
class RealLLMClient(LLMClient):
    def __init__(self, api_key: str, model: str = "gpt-4"):
        self._api_key = api_key   # 仅存于内存，不暴露
        self._model = model
        # 初始化 HTTP 客户端...

    def generate(self, prompt: str) -> str:
        # 调用 LLM API...
```

- `api_key` 为私有属性，无 getter/setter 暴露
- `__repr__` / `__str__` 屏蔽 key 内容

### 8.3 MockLLMClient

```python
class MockLLMClient(LLMClient):
    def __init__(self, action_queue: list[Action]):
        self._queue = list(action_queue)  # 拷贝，防止外部变异

    def generate(self, prompt: str) -> str:
        if not self._queue:
            action = Action("Stop", {"reason": "队列耗尽"})
        else:
            action = self._queue.pop(0)
        return action.to_llm_response()   # 序列化为 LLM 响应文本
```

- 每个测试用例独立构造 `MockLLMClient` 实例，无共享状态
- 支持并发运行单元测试而不互相污染

### 8.4 单测编排示例

```python
def test_guardrail_blocks_escape_write():
    queue = [
        Action("Write_File", {"path": "../etc/passwd", "content": "hacked"}),
        Action("Stop", {"reason": "done"}),
    ]
    mock_llm = MockLLMClient(queue)
    state = AgentState(task="test escape write", ...)
    agent = AgentOS(llm=mock_llm, toolbox=..., guardrail=..., workspace="/tmp/sandbox")
    agent.run(state)

    # 断言: trajectory 第一条记录的 guardrail_result.blocked == True
    assert state.trajectory[0].guardrail_result.blocked
    assert "逸散" in state.trajectory[0].guardrail_result.reason
```

---

## 9. 凭据安全

### 9.1 录入流程

```
启动 AgentOS
  ├── 尝试从 .env 加载 LLM_API_KEY
  │     ├── 成功 → 使用环境值
  │     └── 失败 → 触发 getpass.getpass("请输入 API Key: ")
  │                   → 隐藏输入，不回显
  └── 将 key 传入 RealLLMClient(api_key=key)
       → 原变量立即 del，减少内存驻留窗口
```

### 9.2 安全红线

- `.env` 文件必须列入 `.gitignore`，严禁提交
- API Key **绝不**出现在：
  - `AgentState` 的任何字段
  - `trajectory` 的 observation
  - `error_logs` 的 message
  - 任何日志输出（`print`, `logging`, stdout/stderr）
  - 任何异常的 traceback
- `RealLLMClient` 实例销毁时（`__del__` 或上下文管理器退出）主动覆写内存中的 key

---

## 10. 测试策略

### 10.1 测试层级

| 层级 | 目标 | 工具 | 是否需 Mock LLM |
|------|------|------|----------------|
| 单元测试 | GuardrailEngine 各规则 | pytest | 否（纯函数） |
| 单元测试 | FeedbackController 逻辑 | pytest | 否（纯函数） |
| 单元测试 | Agent 主循环决策链 | pytest + MockLLMClient | **是** |
| 集成测试 | RealLLMClient 真实调用 | pytest | 否（需 API Key） |

### 10.2 确定性单元测试覆盖场景

1. **护栏拦截测试**：构造逸散路径 → 断言 `GuardrailResult.blocked == True`
2. **命令白名单测试**：构造恶意命令（含 `;` `&&` `|` `` ` `` `\n`）→ 断言拦截；构造含合法参数命令（`pytest tests/foo.py -x -v`）→ 断言放行；构造非法基准程序（`python`、`bash`）→ 断言拦截
3. **正常执行链路**：合法动作队列 → 断言文件正确写入、测试正确执行
4. **失败回灌测试**：Mock Execute_Test 返回非零 → 断言 error_logs 被填充
5. **死循环中断测试**：连续 N 次相同错误 → 断言 `AgentLoopDeadError` 抛出
6. **Mock 队列耗尽**：空队列 → 断言自动生成 `Stop` 动作

---

## 11. 分发与部署

### 11.1 交付形态

**Docker 镜像** (`agentos:latest`)

```
docker run --rm \
  -v "$(pwd):/workspace" \
  -e LLM_API_KEY=sk-... \
  agentos:latest \
  --task "修复 tests/test_app.py 中失败的测试用例"
```

### 11.2 Docker 设计要点

- 基础镜像：`python:3.12-slim`
- 容器内预装 `pytest`、`node`（按需）
- 宿主机工作目录挂载到容器 `/workspace`
- 容器内 Agent 锁定 `/workspace` 为工作区根目录（路径围栏以此为锚点）
- API Key 通过环境变量传入，容器退出即消失
- 超时机制：`docker run --timeout 300` 防止任务无限执行

### 11.3 构建脚本

```
docker build -t agentos:latest -f docker/Dockerfile .
```

---

## 12. 项目文件结构

```
agentos-workbench/
├── SPEC.md                       # 本规约文档
├── opencode.json
├── .gitignore                    # 屏蔽 .env
├── .env.example                  # 模板（不含真实 Key）
├── docker/
│   ├── Dockerfile
│   └── entrypoint.sh
├── agentos/
│   ├── __init__.py
│   ├── main.py                   # CLI 入口
│   ├── core/
│   │   ├── __init__.py
│   │   ├── agent.py              # AgentOS 主循环
│   │   ├── state.py              # AgentState 数据结构
│   │   ├── action.py             # Action 定义 + 解析
│   │   └── loop.py               # 主循环调度器
│   ├── llm/
│   │   ├── __init__.py
│   │   ├── interface.py          # LLMClient ABC
│   │   ├── real.py               # RealLLMClient
│   │   └── mock.py               # MockLLMClient
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── toolbox.py            # Toolbox 注册 + 调度
│   │   ├── read_file.py
│   │   ├── write_file.py
│   │   └── execute_test.py
│   ├── guardrail/
│   │   ├── __init__.py
│   │   ├── engine.py             # GuardrailEngine
│   │   └── rules.py              # 各规则实现
│   ├── feedback/
│   │   ├── __init__.py
│   │   ├── controller.py         # FeedbackController
│   │   └── extractor.py          # Traceback 结构化提取
│   └── security/
│       ├── __init__.py
│       └── credentials.py        # .env 读取 + getpass 交互
└── tests/
    ├── __init__.py
    ├── test_guardrail_rules.py
    ├── test_feedback_controller.py
    ├── test_agent_loop.py        # 使用 MockLLMClient
    └── fixtures/
        └── mock_actions.py
```

---

## 13. 术语表

| 术语 | 英文 | 定义 |
|------|------|------|
| 主循环 | Main Loop | Agent 的核心调度循环：Context → Call → Parse → Guard → Execute → Feedback |
| 护栏 | Guardrail | 硬代码实现的执行前安全拦截规则 |
| 回灌 | Feedback Loop | 将执行失败的结构化错误信息注入下一轮 LLM Prompt 的闭环机制 |
| 死循环 | Dead Loop | 连续 N 次完全相同错误，判定为修正无效的系统状态 |
| 动作队列 | Action Queue | MockLLMClient 内部预置的确定性动作序列，用于单测编排 |
| 结构化注入 | Structured Injection | 将原始 Traceback 解析为 `{errorType, message, location}` 三元组后再注入 Prompt |

---

## 14. 附录：失败回灌完整状态机

```
                         ┌──────────┐
                         │  Execute  │
                         │  Test     │
                         └────┬─────┘
                              │
                    exit_code == 0? ──yes──→ 成功，继续下一轮
                              │
                             no
                              │
                    ┌─────────▼─────────┐
                    │ 提取 ErrorEntry   │
                    │ 写入 error_logs   │
                    └─────────┬─────────┘
                              │
                    ┌─────────▼─────────┐
                    │ retry_count >= N? │
                    └─────────┬─────────┘
                     yes│          │no
                        │          │
              ┌─────────▼──┐    ┌──▼───────────┐
              │ 检查连续   │    │ retry_count++ │
              │ N 次相同?  │    │ 继续重试      │
              └─────┬──────┘    └───────────────┘
                 yes│       no
                    │        │
          ┌─────────▼──┐  ┌──▼───────────┐
          │ 抛出       │  │ retry_count  │
          │ DeadLoop   │  │ = 0 (重置)   │
          │ Error      │  │ 继续重试      │
          └────────────┘  └──────────────┘
```
