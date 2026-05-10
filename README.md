<p align="center">
  <img src="https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-3B82F6?style=for-the-badge" alt="Platform">
  <img src="https://img.shields.io/badge/Python-3.9%2B-3776AB?style=for-the-badge&logo=python" alt="Python">
  <img src="https://img.shields.io/badge/License-MIT-success?style=for-the-badge" alt="License">
  <img src="https://img.shields.io/badge/Codex_↔_OpenCode-Bridge-10B981?style=for-the-badge" alt="Bridge">
</p>

# 🧠 Codex Memory Sync

<p align="center">
  <b>你的 AI 编程助手，不应该每台设备都是"新来的实习生"。</b>
  <br><br>
  <i>让 Codex 和 OpenCode 记住你的一切——项目理解、对话上下文、工作偏好。<br>跨设备、跨工具、跨平台，一次配置，终身跟随。</i>
</p>

<br>

---

## 🤔 一个好问题

> 你在台式机上花了两周和 Codex 讨论项目架构。它理解了你的分层设计、记住了你的命名习惯、积累了几百轮有深度的技术对话。
>
> 然后你换了台笔记本。
>
> 它不认识你了。

不是模型的问题。是**上下文断了**。每次换设备、每次换工具，你都要重新描述、重新解释、重新教它。这些重复的 Token 消耗、重复的时间成本，原本一笔勾销。

**Codex Memory Sync 就是为此而生。**

<br>

---

## 🎯 它做什么

<p align="center">
  <table>
    <tr>
      <td align="center" width="33%">
        <h3>🔄 跨设备同步</h3>
        <p>公司台式机 → 家里笔记本 → 远程服务器<br>AI 认知状态无缝流转</p>
      </td>
      <td align="center" width="33%">
        <h3>🔗 跨工具移植</h3>
        <p>Codex ↔ OpenCode<br>积攒的上下文不被任何平台绑架</p>
      </td>
      <td align="center" width="33%">
        <h3>📦 离线容灾</h3>
        <p>加密导出 → U 盘拷贝<br>不依赖网络，不依赖云服务</p>
      </td>
    </tr>
  </table>
</p>

<br>

---

## ✨ 为什么你应该立刻用它

### 🧠 你的每次对话，都是在为 AI 积累"记忆"

你在 Codex 里让 AI 记住的项目规范、架构决策、命名偏好——这些不是"临时指令"，是你的**数字认知资产**。每次换设备就清零，等于你花掉的 Token 和时间打了水漂。

Codex Memory Sync 像 iCloud 对照片做的那样——自动打包、加密、同步你的 AI 记忆。打开新设备，AI 就像从没离开过一样。

### 💬 上百轮深度对话，不应该像聊天记录一样被遗忘

一段复杂的调试对话、一个深思熟虑的架构讨论、一次漫长的问题排查——都是投入了大量时间和 Token 换来的智力成果。Codex Memory Sync 完整保留它们，支持：

- `.jsonl` 格式的完整对话提取——**连思考过程都保留**
- SQLite 格式的 OpenCode 会话——**按工作目录清晰分组**
- 聊天气泡式预览——**一目了然，不用翻原始 JSON**

### 🔄 你不应该被一个 AI 工具锁死

Codex 用腻了想试试 OpenCode？OpenCode 的某个功能不在 Codex 里？**不用从零开始教新工具。** Codex Memory Sync 是业内首个支持两大 AI 编程助手双向记忆移植的工具：

```
Codex                      OpenCode
─────                      ────────
AGENTS.md       ────────→  AGENTS.md
skills/         ←────────  skills/
sessions/*.jsonl ←─→      SQLite session/message/part
memories/*.md   ────────→  instructions[]
todo 任务       ←────────  项目级待办项
```

### 📂 你的项目是按目录组织的，记忆也该如此

OpenCode 的原生数据把所有会话堆在"global"里，毫无逻辑。Codex Memory Sync 按**真实工作目录**重组一切：

```
📁 D:\projects\电商平台     (8 sessions, 609 messages)
📁 D:\client-work\金融后台   (2 sessions, 428 messages)
📁 D:\learning\算法练习      (1 session, 51 messages)
```

**和你大脑里的项目概念完全一致。** 不再翻混乱的 global 列表。

### 🔒 安全不应该是一个"可选功能"

- **AES-256-GCM** 军用级加密——你的对话只有你能看
- 导出包可设密码保护——U 盘丢了数据也不会泄露
- 导入 OpenCode SQLite 前**自动备份**——万无一失
- 纯本地模式——**数据从不出你的设备**，不需要任何云服务

### 🎨 你值得一个好看的控制面板

<p align="center">
  <b>Web 端推荐使用</b> —— 功能最全，体验最好。<br>
  <img src="https://img.shields.io/badge/暗色/亮色-一键切换-3B82F6?style=flat-square">
  <img src="https://img.shields.io/badge/响应式-适配手机/平板-10B981?style=flat-square">
  <img src="https://img.shields.io/badge/零依赖-纯HTML/CSS/JS-F59E0B?style=flat-square">
</p>

| | 传统做法 | Codex Memory Sync |
|---|---|---|
| **换设备迁移** | 手动找目录、手动拷、手动恢复 | 一键导出 → 双击导入脚本 |
| **跨工具迁移** | 不可能，重头开始 | 勾选会话 → 一键注入 |
| **数据安全** | 裸文件随便拷 | AES-256-GCM 加密 |
| **会话预览** | 打开原始 JSON 手动看 | 聊天气泡时间线 + 思考折叠 |
| **项目组织** | 全部堆一起 | 按工作目录清晰分组 |
| **自动同步** | 不存在 | 后台守护进程实时监听 |
| **颜值** | 命令行 + 记事本 | Web Dashboard + 桌面 GUI |

<br>

---

## 🚀 开箱即用，三步跑起来

```bash
# 1. 克隆
git clone https://github.com/YMY0730/codex-memory-sync.git
cd codex-memory-sync

# 2. 安装
pip install -e .

# 3. 启动 Web 控制台（推荐）
python web_server.py
```

浏览器打开 **http://127.0.0.1:8899**，三分钟内完成第一次跨设备迁移。

| 启动方式 | 命令 | 适合 |
|----------|------|------|
| **🌐 Web 控制台** | `python web_server.py` | **推荐** · 功能最全 · 可远程 |
| 🖥️ 桌面 GUI | `python cli.py gui` | 习惯桌面应用 |
| ⌨️ 命令行 | `codex-memory bridge c2o --all` | 脚本/自动化 |

<br>

---

## ⚡ 真实场景

> **场景一：你在公司台式机上用 Codex 做了一个月的项目。**
>
> → 导出加密 ZIP，带回家，双击 `import.bat`。笔记本上的 Codex 立刻认识了你的项目架构。

> **场景二：你想从 Codex 换到 OpenCode 试试。**
>
> → Web 控制台打开 🔄 跨工具，勾选要迁移的会话，点一下。OpenCode 里出现了你全部的对话历史，包括思考过程。

> **场景三：你有 5 个 OpenCode 工作目录，想整理一下。**
>
> → 💬 会话浏览，5 个目录自动分组显示。点击任一会话，右侧完整聊天时间线。选中的一键导出为 Codex 可读格式。

<br>

---

## 📊 数据说明

| 模块 | 做什么 |
|------|--------|
| `src/chat_parser.py` | Codex `.jsonl` → 结构化消息（user/assistant/thinking/tool/meta/event 六类） |
| `src/bridge.py` | Codex ↔ OpenCode SQLite 双向转换引擎（600+ 行） |
| `src/path_detector.py` | 跨设备自动检测 `.codex` 目录位置 |
| `src/exporter.py` | AES-256-GCM 加密打包 + 内置导入脚本生成 |
| `src/daemon.py` | 后台文件监听 + 自动推送/拉取 |

<br>

---

## 📄 License

MIT © YMY0730

<p align="center">
  <sub>Made with ❤️ for the AI coding community. Star this repo if it saves you time and tokens.</sub>
</p>
