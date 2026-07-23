# AgentOS — Coding Agent Harness

> AI4SE 期末大作业 · 项目 A  
> 从零手写的 LLM Agent 主循环基础设施

---

## 项目简介

AgentOS 是一个从零手写的 **Coding Agent 主循环引擎**（Harness），严格禁用 LangChain/AutoGen 等框架。它接收自然语言编程任务（如"修复这个 bug"），自主调用受控工具读写文件、执行测试，在硬代码护栏下安全运行，并通过结构化错误回灌驱动 LLM 自我修正。

### 核心流水线

主循环按以下五阶段严格串行执行：

```
① Context Assembly → ② LLM Call → ③ Parse → ④ Guardrail → ⑤ Execute
     ↑                                                    │
     └────────── ⑥ Feedback (Execute_Test 失败时) ─────────┘
```

| 阶段 | 职责 |
|------|------|
| **Context Assembly** | 将 `AgentState`（对话历史 + 执行轨迹 + 错误日志）组装为 Prompt |
| **LLM Call** | 调用 `LLMClient.generate(prompt)` 获取响应 |
| **Parse** | 解析 LLM 响应为结构化 `Action` 对象 |
| **Guardrail** | 硬代码校验（路径围栏 / 命令白名单），拦截即阻断 |
| **Execute** | 执行合法动作（Read\_File / Write\_File / Execute\_Test） |
| **Feedback** | 测试失败时结构化提取 Traceback，注入下一轮 Prompt 驱动修正 |

### 架构红线（已验证）

- ✅ **零框架依赖** — 主循环纯手写，无 LangChain/AutoGen
- ✅ **硬代码安全机制** — 护栏和回灌逻辑为 Python 硬代码，非提示词控制
- ✅ **Mock 注入测试** — 35 个单测全部通过 `MockLLMClient` 脱机确定性运行
- ✅ **API Key 内存隔离** — 凭据仅存于 `RealLLMClient` 私有属性，`__repr__`/`__str__` 零泄漏

---

## 安装与运行

### 本地安装

```bash
pip install .
```

### CLI 使用

```bash
agentos --task "修复 tests/test_app.py 中失败的测试用例"
```

程序将优先读取 `.env` 文件获取 `LLM_API_KEY`，若未找到则通过 `getpass` 安全交互式输入。

### WebUI 使用 (Gradio)
提供基于网页的可视化交互界面（兼容魔搭等云端托管平台部署）：
```bash
python app.py
```
WebUI链接：https://www.modelscope.cn/studios/Yiokkk/agentos

### 运行测试

```bash
pip install pytest
python -m pytest tests/ -v -k "not integration"
```

所有 34 个单测均使用 `MockLLMClient`，无需 API Key，拔网线也可 100% 稳定通过。

---

## 容器化分发

Docker 镜像使用 `python:3.12-slim` 多架构基础镜像，兼容 Intel / ARM 硬件环境。

### 构建

```bash
docker build -t agentos:latest -f docker/Dockerfile .
```

### 运行

```bash
docker run --rm \
  -v "$(pwd):/workspace" \
  -e LLM_API_KEY=sk-... \
  agentos:latest \
  --task "修复 tests/test_app.py 中失败的测试用例"
```

容器内 `Execute_Test` 预装 `pytest`，工作区锚点 `/workspace` 与路径围栏严格对齐。

---

## 目录结构

```
agentos-workbench/
├── SPEC.md                       # 规约文档
├── PLAN.md                       # 实现计划
├── .gitlab-ci.yml                # CI/CD 流水线
├── docker/
│   ├── Dockerfile                # 多架构 Docker 构建
│   └── entrypoint.sh
├── agentos/
│   ├── main.py                   # CLI 入口
│   ├── core/
│   │   ├── agent.py              # AgentOS 主循环
│   │   ├── state.py              # AgentState 数据结构
│   │   ├── action.py             # Action 定义
│   │   └── loop.py               # 主循环调度器
│   ├── llm/
│   │   ├── interface.py          # LLMClient ABC
│   │   ├── real.py               # RealLLMClient
│   │   └── mock.py               # MockLLMClient
│   ├── tools/
│   │   ├── toolbox.py            # 工具调度器
│   │   ├── read_file.py
│   │   ├── write_file.py
│   │   └── execute_test.py
│   ├── guardrail/
│   │   ├── engine.py             # GuardrailEngine
│   │   └── rules.py              # 路径围栏 / 命令白名单
│   ├── feedback/
│   │   ├── controller.py         # 重试控制 + 死循环检测
│   │   └── extractor.py          # Traceback 结构化提取
│   └── security/
│       └── credentials.py        # .env + getpass 安全录入
└── tests/
    ├── test_state.py             # 数据结构单测
    ├── test_mock_llm.py          # Mock LLM 单测
    ├── test_real_llm.py          # 集成测试（CI 中跳过）
    ├── test_tools.py             # 工具安全单测
    ├── test_guardrail_rules.py   # 护栏规则单测
    ├── test_feedback_controller.py # 回灌逻辑单测
    └── test_agent_loop.py        # 主循环端到端单测
```

---

## 安全边界与凭据配置

> 本节为本项目安全架构的核心得分点。

### API Key 内存隔离

AgentOS 严格遵循 **不落盘、不序列化、不日志、不泄漏** 的四不原则：

1. **私有属性**：API Key 存储为 `RealLLMClient._api_key`，Python 命名约定阻止意外外部访问
2. **防泄漏输出**：`__repr__` 和 `__str__` 均已重写，返回 `RealLLMClient(model=gpt-4)`，**绝不会**将 Key 内容带入任何字符串表示
3. **生命周期终结**：`__del__` 方法将 `_api_key` 覆写为 `"INVALIDATED"`，缩短内存驻留窗口
4. **绝对不入 `AgentState`**：Key 不会出现在对话历史、执行轨迹、错误日志或异常 Traceback 中
5. **不入日志**：任何 `print`/`logging` 输出均不含凭据

### 凭据配置方式（目标机器操作步骤）

在运行 AgentOS 的机器上，按以下步骤安全配置 LLM API Key：

```bash
# 1. 创建 .env 文件（已列入 .gitignore，不会被提交）
echo "LLM_API_KEY=sk-your-key-here" > .env

# 2. 直接运行（自动读取 .env）
agentos --task "..."

# 3. 若无 .env，程序会触发 getpass 静默输入（不回显）
```

**禁止行为：**
- ❌ 不得将 `.env` 提交到 Git 仓库
- ❌ 不得在命令行中使用 `export LLM_API_KEY=xxx`（明文暴露）
- ❌ 不得在代码中硬编码 Key

### 治理护栏

| 规则 | 适用范围 | 拦截逻辑 |
|------|----------|----------|
| **G1 路径围栏** | `Read_File` / `Write_File` | 禁止写出工作区，禁止访问 `/etc/` 等系统目录，禁止软链接逃逸 |
| **G2 命令白名单** | `Execute_Test` | 基准程序仅允许 `npm test` / `pytest`，拦截 `;` `&&` `|` `` ` `` `\n` 等注入字符 |

### 失败回灌与死循环保护

```
Execute_Test 非零退出 → 正则提取 {error_type, message, location}
→ 写入 AgentState.error_logs
→ 连续 3 次完全相同错误 → AgentLoopDeadError 硬中断
→ 出现新异类错误 → 重置计数继续重试
```

---

## 已知限制

- **Python >= 3.12**：项目使用 `str | None` 联合类型语法和 `list` 泛型
- **仅支持 OpenAI 兼容 API**：当前代码默认直连学校网关 `https://njusehub.info/v1`，如需使用官方或其他兼容代理，请在代码中修改 `base_url`。
- **`Execute_Test` 白名单固定为 `npm test` / `pytest`**：如需扩展命令集，需修改 `guardrail/rules.py` 中的 `ALLOWED_BASES`
- **项目工作区锚定当前目录**：CLI 运行时 `workspace = os.path.abspath(".")`，所有路径操作均以此为界
