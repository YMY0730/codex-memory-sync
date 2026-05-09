# 🧠 Codex Memory Sync

> **AI 的记忆不该被困在一台机器里。跨设备、跨工具、跨平台——让你的 AI 认知资产自由流动。**

Codex Memory Sync 是全球首个支持 **Codex ↔ OpenCode 双向记忆移植** 的开源基础设施。它不仅解决了 Codex 用户在多台设备间同步记忆和上下文的刚需，更首次打通了 Codex 与 OpenCode 之间的认知壁垒——你在 Codex 里花数周积累的项目理解、架构决策、会话上下文，可以一键注入 OpenCode，反过来一样。**告别每换一个工具就从头教 AI 的时代。**

---

## 💡 为什么你需要它

AI 编程助手的核心瓶颈不是模型能力，而是 **上下文断裂**。你在台式机上花了三周让 Codex 理解你的项目架构，换到笔记本上它就变成了一个从零开始的实习生。你切换到 OpenCode 想试试新体验，之前积累的全部对话历史和规则瞬间归零。

Codex Memory Sync 用三层能力彻底解决这个问题：

1. **设备间同步** — 加密记忆包在多台电脑间自动流转
2. **工具间移植** — Codex ↔ OpenCode 双向导入，AGENTS.md、Skills、会话记录一行命令带走  
3. **离线容灾** — 导出加密 ZIP，U 盘拷贝即用，不依赖任何云服务

---

## 🔑 核心特性

| 特性 | 说明 |
|------|------|
| 🧠 **记忆同步** | 项目规范、架构决策、命名偏好，一次配置全设备共享 |
| 💬 **会话搬运** | 完整对话记录+思考链路，`.jsonl` ↔ SQLite 双向转换 |
| 🔄 **跨工具桥接** | Codex ↔ OpenCode：AGENTS.md、Skills、Memories、Sessions 一键移植 |
| 🔒 **端到端加密** | AES-256-GCM，密钥从不出设备；导出 ZIP 可选密码保护 |
| 📂 **本地优先** | 无需任何云后端即可完整使用，导出 `.zip` / `.codex` 离线带走 |
| 🎨 **双界面** | CustomTkinter 桌面 GUI + FastAPI Web Dashboard，亮色/暗色主题 |
| 💬 **聊天时间线** | `.jsonl` 会话渲染为可视气泡：用户/助手/思考/工具六类区分 |
| 🤖 **守护进程** | 后台监听文件变化，自动推送/拉取，无需人工干预 |
| 📦 **桌面 + Web + CLI** | GUI、浏览器、命令行三种交互方式任意切换 |

---

## 📦 快速开始

```bash
# 安装
pip install -e .

# 桌面 GUI（最完整）
start_gui.bat        # Windows
./start_gui.sh       # macOS / Linux

# Web 控制台
start_web.bat        # 浏览器访问 http://127.0.0.1:8899
./start_web.sh       # macOS / Linux

# CLI 命令行
codex-memory status               # 查看状态
codex-memory export               # 导出 ZIP
codex-memory bridge c2o --all     # Codex → OpenCode 一键导入
codex-memory bridge o2c --all     # OpenCode → Codex 一键导出
```

---

## 🏗️ 架构

```
┌─────────────────────────────────────────────────────────┐
│  交互层                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ 桌面 GUI      │  │  Web 控制台   │  │  CLI 命令行   │  │
│  │ CustomTkinter │  │ FastAPI+HTML │  │ Click        │  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  │
├─────────┼─────────────────┼─────────────────┼───────────┤
│  业务层  │                 │                 │           │
│  ┌──────┴─────────────────┴─────────────────┴───────┐   │
│  │ chat_parser  │ bridge    │ exporter  │ daemon   │   │
│  │ JSONL→气泡   │ CX↔OC    │ AES-GCM   │ watchdog │   │
│  └──────────────────────────────────────────────────┘   │
├─────────────────────────────────────────────────────────┤
│  存储层                                                  │
│  ┌─────────┐  ┌───────────┐  ┌──────────────────────┐  │
│  │ Codex   │  │ OpenCode  │  │ 云后端 (GitHub/MBaOut)│  │
│  │ JSONL   │  │ SQLite    │  │ NoopBackend (本地)    │  │
│  └─────────┘  └───────────┘  └──────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

---

## 🔄 跨工具桥接

```
Codex (~/.codex/)                    OpenCode (opencode.db)
┌──────────────────┐                ┌──────────────────────┐
│ AGENTS.md        │ ←── 双向 ──→ │ ~/.config/opencode/   │
│ skills/          │ ←── 目录 ──→ │ AGENTS.md             │
│ sessions/YYYY/MM │ ←── JSONL ──→│ skills/               │
│   *.jsonl        │     ↕         │ session + message     │
│ memories/*.md    │ ── 追加 ──→  │   + part 表           │
│ session_index    │     SQLite    │                       │
└──────────────────┘                └──────────────────────┘
```

---

## 🔒 安全模型

- **加密算法**：AES-256-GCM，每包独立随机 Salt（16B）+ Nonce（12B）
- **密钥派生**：PBKDF2-HMAC-SHA256，600,000 迭代
- **包格式**：`[1B version][16B salt][12B nonce][ciphertext]`
- **传输安全**：云后端只存储无法解析的二进制 blob

> ⚠️ 加密密码本地明文存储在 `~/.codex-memory-sync/config.json`（守护进程需无人值守）。未来将集成系统密钥链。

---

## 🧪 质量保证

```bash
ruff check   # 零错误
ruff format  # 全量格式化
pyright      # 严格类型检查，零错误零警告
```

GitHub Actions CI 自动在 Python 3.11 / 3.12 上验证每次提交。

---

## 📄 License

MIT © YMY0730
