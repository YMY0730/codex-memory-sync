# 🧠 Codex Memory Sync

> **Codex ↔ OpenCode 双向记忆移植基础设施。把 AI 对你的项目认知，像 Git 一样推送到任何地方。**

Codex Memory Sync 是全球首个打通 **Codex 和 OpenCode 认知壁垒** 的开源工具。它不仅能在多台设备间同步记忆和上下文，更实现了两大 AI 编程助手之间的**完整对话记录移植**——Codex 的会话可以一键注入 OpenCode，OpenCode 的每个工作目录可以一键导出为 Codex 可读的完整对话。

**强烈推荐使用网页端**，功能最全、体验最好、无需安装任何桌面环境。

---

## 🚀 快速开始

```bash
# 一键启动 Web 控制台（推荐）
cd codex-memory-sync
pip install -e .
python web_server.py
# → 浏览器打开 http://127.0.0.1:8899
```

**Web 端功能一览：**
- 📊 仪表盘 — Codex + OpenCode 数据概览
- 💻 本地文件 — Codex 文件树浏览 + 聊天时间线预览
- 💬 会话浏览 — Codex JSONL + OpenCode 按工作目录分组的全量会话
- 🔄 跨工具 — 复选框选择性导入导出（Codex ↔ OpenCode）
- 📦 导出 — ZIP 压缩包（可选 AES-256 密码）
- 🌙 暗色/亮色主题一键切换

---

## ✨ 为什么选择 Web 端

| 对比 | 桌面 GUI | Web 端 |
|------|----------|--------|
| 安装依赖 | 需要 tkinter + CustomTkinter | 仅需 `pip install -e .` |
| 远程访问 | 不支持 | 局域网/内网穿透即可 |
| OpenCode 浏览 | 基础项目树 | 按工作目录分组 + 完整聊天预览 |
| 跨工具导入 | 批量操作 | 逐条勾选 + 进度反馈 |
| 更新 | 需重新打包 | 刷新浏览器即可 |
| 外观 | 单主题 | 暗色/亮色实时切换 |

---

## 🔑 核心特性

| 特性 | 说明 |
|------|------|
| 🧠 **记忆同步** | 项目规范、架构决策、命名偏好，一次配置全设备共享 |
| 💬 **全量会话搬运** | Codex `.jsonl` ↔ OpenCode `SQLite`，完整对话+思考链路双向转换 |
| 🔄 **跨工具桥接** | Codex ↔ OpenCode：AGENTS.md、Skills、Memories、Sessions 一键移植 |
| 📂 **按工作目录组织** | OpenCode 会话按 `D:\projects\foo`、`D:\projects\bar` 等目录清晰分组 |
| 🔒 **端到端加密** | AES-256-GCM，密钥从不出设备；导出 ZIP 可选密码保护 |
| 📂 **本地优先** | 无需任何云后端，导出 `.zip` / `.codex` 离线带走 |
| 🎨 **三界面** | Web Dashboard（推荐） + 桌面 GUI + CLI 命令行 |
| 💬 **聊天时间线** | `.jsonl` + OpenCode 会话 → 可视气泡：用户/助手/思考/工具六类区分 |

---

## 📦 CLI 快速命令

```bash
# Codex → OpenCode（勾选会话导入）
codex-memory bridge c2o --all

# OpenCode → Codex（按项目完整导出，含 session_index）
codex-memory bridge o2c --all

# 本地 ZIP 导出
codex-memory export

# 查看状态
codex-memory status
codex-memory bridge list
```

---

## 🏗️ 架构

```
┌──────────────────────────────────────────────────────────┐
│  🌐 Web Dashboard (FastAPI + HTML5)  ← 推荐入口          │
│  🖥️ 桌面 GUI (CustomTkinter)                              │
│  ⌨️ CLI (Click)                                          │
├──────────────────────────────────────────────────────────┤
│  src/chat_parser.py  — Codex .jsonl → 结构化消息          │
│  src/bridge.py       — Codex ↔ OpenCode SQLite 双向引擎   │
│  src/path_detector.py — 跨设备自动检测 .codex 目录        │
│  src/exporter.py     — AES-256-GCM 加密打包               │
│  src/daemon.py       — 后台文件监听 + 自动同步             │
├──────────────────────────────────────────────────────────┤
│  Codex (~/.codex/)        OpenCode (opencode.db)          │
│  └─ sessions/YYYY/MM/*.jsonl   └─ session/message/part   │
│     memories/*.md                  project/todo           │
│     rules/                         per-directory grouped  │
└──────────────────────────────────────────────────────────┘
```

---

## 🔒 安全模型

- **加密算法**：AES-256-GCM，每包独立随机 Salt（16B）+ Nonce（12B）
- **密钥派生**：PBKDF2-HMAC-SHA256，600,000 迭代
- **包格式**：`[1B version][16B salt][12B nonce][ciphertext]`
- **导入保护**：操作 OpenCode SQLite 前自动备份 → `.db.bak`

---

## 🧪 质量保证

```bash
ruff check   # 零错误
ruff format  # 全量格式化
pyright      # 严格类型检查，零错误零警告
```

---

## 📄 License

MIT © YMY0730
