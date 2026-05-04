# Chatter

基于 [ncatbot](https://pypi.org/project/ncatbot/) 的 QQ 群聊角色扮演机器人。使用 DeepSeek API（Anthropic 协议）作为 LLM 后端，模拟真实用户的聊天行为。

## 特性

- **三频率 tick 架构**：被动回复(3s)、主动发言(60s)、记忆浓缩(300s)
- **六层主动发言抑制链**：时间、能量、社交电量、频率、LLM 意图判断、发送前检查
- **情绪系统**：valence / energy / social_battery 动态变化
- **三层记忆模型**：未读 → 已读 → 待浓缩，长期记忆 SQLite 持久化
- **紧急刹车**：空消息、过长、AI 句式检测、频率限制
- **降级模式**：LLM 连续失败自动切换模板回复，恢复后自动回到正常模式
- **延迟发送**：截断正态分布模拟人类回复节奏

## 环境要求

- Python 3.12.9（推荐使用 conda `bot` 环境）
- ncatbot 3.8.8+

## 安装

```bash
# 克隆项目
git clone <repo-url>
cd ncatbot-chatter

# 创建 conda 环境（如已有可跳过）
conda create -n bot python=3.12.9
conda activate bot

# 安装依赖
pip install -r requirements.txt

# 复制配置模板
cp conf/bot.yaml.template conf/bot.yaml
cp conf/character.yaml.template conf/character.yaml
cp conf/group_name.yaml.template conf/group_name.yaml
```

## 配置

编辑 `conf/bot.yaml`：

```yaml
bot_uin: "你的机器人QQ号"
root_uin: "管理员QQ号"

# LLM API 配置（Anthropic 协议）
api_key: "你的 DeepSeek API Key"
base_url: "https://api.deepseek.com/anthropic"
model: "deepseek-v4-pro"
```

### 环境变量方式

也可以通过环境变量配置（优先级高于 yaml）：

```bash
export ANTHROPIC_BASE_URL=https://api.deepseek.com/anthropic
export ANTHROPIC_AUTH_TOKEN=你的DeepSeek-API-Key
export ANTHROPIC_MODEL=deepseek-v4-pro
```

### 角色配置

编辑 `conf/character.yaml` 设置机器人角色人设。模板见 `conf/character.yaml.template`。

### 群名映射

编辑 `conf/group_name.yaml` 设置群号到群名的映射。

## 运行

```bash
python main.py
```

启动后，机器人进入 RUNNING 模式：
- 每 3 秒检查被动消息（@bot / 私聊 / 提及）
- 每 60 秒检查主动发言意图
- 每 300 秒执行记忆浓缩

### 模拟运行

不需要真实 QQ 账号，使用 mock 模拟：

```bash
python scripts/run_sim.py
```

### 日志分析

```bash
python scripts/analyze_logs.py [data/action_log.db]
```

输出：状态分布、触发类型、延迟统计、时间分布、状态机完整性。

## 测试

```bash
# 运行全部单元测试
python -m pytest tests/ -v

# 运行集成测试
python -m pytest tests/test_integration.py -v

# 运行 E2E 测试（需要真实 API）
RUN_E2E_LLM=1 python -m pytest tests/test_e2e.py -v
```

## 架构

```
main.py → build_app() → 注册 ncatbot 回调 → MainLoop 三频率 tick
                                            ↓
ncatbot callback → IncomingMessageQueue.put(raw_event)
                    ↓
         MessageIngestor.drain() → parse / dedup / MemoryManager
                    ↓
         Orchestrator
           ├─ run_passive_tick()   每 3s
           ├─ run_active_tick()    每 60s
           └─ run_concentrate_tick() 每 300s
                    ↓
         DecisionEngine → ActionPlan[]
                    ↓
         ContentGenerator / DegradedReplyPolicy → GeneratedAction[]
                    ↓
         EmergencyBrake.final_check()
                    ↓
         DelaySendScheduler → BotAdapter.send()
                    ↓
         ActionLog + StateEventQueue → BotState.apply()
```

### 目录结构

```
conf/           配置文件（schema, loader, templates）
core/           核心逻辑（state, decision, orchestrator, main_loop）
generation/     生成系统（content_gen, formatter）
infra/          基础设施（llm_client, bot_adapter, action_log, message_ingestor）
memory/         记忆系统（short_term, long_term, concentrator, relationship, entity）
ui/             发送调度（sender）
scripts/        工具脚本（run_sim, analyze_logs）
tests/          测试文件
```

### 关键设计约束

| 约束 | 说明 |
|---|---|
| DecisionEngine 禁止调用 ContentGenerator | 决策与生成严格分离 |
| PassiveReplyJudge 禁止调用 LLM | 纯规则判断 |
| BotState 只能由主线程修改 | 通过 StateEventQueue 跨线程通知 |
| ActionLog 状态变更必须幂等 | INSERT OR IGNORE + 状态前置条件 |
| SQLite 独立 connection + WAL 模式 | 跨线程使用时加锁 |
| pre_send_check 禁止调用 LLM | 8 条纯规则 |
| LLM JSON 解析由调用方负责 | Pydantic schema 校验 |

## 运行模式

| 模式 | 被动回复 | 主动发言 | 浓缩 | 生成方式 |
|---|---|---|---|---|
| RUNNING | Yes | Yes | Yes | LLM |
| PASSIVE_ONLY | Yes | No | No | LLM |
| DEGRADED | Yes | No | No | 模板 |
| PAUSED | No | No | No | - |
| ERROR | No | No | No | - |

## API 协议

使用 Anthropic Messages API 格式（`anthropic` SDK），通过 DeepSeek 的 Anthropic 兼容端点接入：

```
POST https://api.deepseek.com/anthropic/v1/messages
```

系统提示词通过 `system` 参数传递，对话消息通过 `messages` 数组传递。

## 许可证

MIT
