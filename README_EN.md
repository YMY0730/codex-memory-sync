<p align="center">
  <img src="https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-3B82F6?style=for-the-badge" alt="Platform">
  <img src="https://img.shields.io/badge/Python-3.9%2B-3776AB?style=for-the-badge&logo=python" alt="Python">
  <img src="https://img.shields.io/badge/License-MIT-success?style=for-the-badge" alt="License">
  <img src="https://img.shields.io/badge/Codex_↔_OpenCode-Bridge-10B981?style=for-the-badge" alt="Bridge">
</p>

<p align="right">
  <a href="README.md">🇨🇳 中文</a> &nbsp;|&nbsp; <b>🇺🇸 English</b>
</p>

# 🧠 Codex Memory Sync

<p align="center">
  <b>Your AI coding assistant shouldn't start every device as "the new intern."</b>
  <br><br>
  <i>Let Codex and OpenCode remember everything — project understanding, conversation context, work habits.<br>Across devices, across tools, across platforms. Configure once, follow you forever.</i>
</p>

<br>

---

## 🤔 The Big Question

> You spent two weeks on your desktop, discussing project architecture with Codex. It learned your layering design, remembered your naming conventions, accumulated hundreds of deep technical conversations.
>
> Then you switched to your laptop.
>
> It doesn't know you anymore.

It's not the model's fault. The **context broke**. Every time you change devices, every time you switch tools, you have to re-describe, re-explain, re-teach. All that wasted token spend, all that wasted time — gone, unless you bridge the gap.

**Codex Memory Sync exists to solve this.**

<br>

---

## 🎯 What It Does

<p align="center">
  <table>
    <tr>
      <td align="center" width="33%">
        <h3>🔄 Cross-Device Sync</h3>
        <p>Desktop → Laptop → Remote Server<br>AI cognitive state transfers seamlessly</p>
      </td>
      <td align="center" width="33%">
        <h3>🔗 Cross-Tool Migration</h3>
        <p>Codex ↔ OpenCode<br>Your context isn't locked to any platform</p>
      </td>
      <td align="center" width="33%">
        <h3>📦 Offline Backup</h3>
        <p>Encrypted export → USB copy<br>No network, no cloud, no dependency</p>
      </td>
    </tr>
  </table>
</p>

<br>

---

## ✨ Why You Need It — Right Now

### 🧠 Every Conversation Is An Asset. Stop Throwing Them Away.

The project conventions, architecture decisions, and naming preferences you taught Codex over days and weeks — these aren't "temporary instructions." They're your **digital cognitive assets**. Every time you switch devices and start over, those tokens and hours are wasted.

Codex Memory Sync does for AI context what iCloud does for photos — packages, encrypts, and syncs automatically. Open a new device, and your AI behaves like it never left.

### 💬 Hundreds of Deep Discussions Deserve Better Than a "Chat History" Tab

A complex debugging thread. A thoughtful architectural debate. A marathon troubleshooting session. Each one represents real intellectual investment. Codex Memory Sync preserves them all:

- `.jsonl` full conversation extraction — **thinking processes included**
- SQLite-based OpenCode sessions — **organized by working directory**
- Chat-bubble timeline preview — **glanceable, not raw JSON**

### 🔄 You Should Never Be Trapped In One AI Tool

Tired of Codex? Curious about OpenCode? Or the other way around? **You shouldn't have to start from scratch teaching a new tool.** Codex Memory Sync is the first open-source solution for bidirectional AI assistant context migration:

```
Codex                              OpenCode
─────                               ────────
AGENTS.md         ──────────→      AGENTS.md
skills/           ←──────────      skills/
sessions/*.jsonl  ←─────→          SQLite session / message / part
memories/*.md     ──────────→      instructions[]
todo items        ←──────────      per-project task list
```

### 📂 Projects Are Organized By Folder. So Should Your Memory.

OpenCode's native data dumps everything into a chaotic "global" bucket. Codex Memory Sync reorganizes by **actual working directory**:

```
📁 D:\projects\ecommerce     (8 sessions, 609 messages)
📁 D:\client-work\fintech    (2 sessions, 428 messages)
📁 D:\learning\algorithms    (1 session, 51 messages)
```

**Maps perfectly to your mental model.** No more digging through a disorganized global list.

### 🔒 Security Is Not Optional

- **AES-256-GCM** military-grade encryption — your conversations, yours alone
- Export packages can be password-protected — lose a USB, data stays safe
- **Auto-backup before modifying SQLite** — zero risk of data corruption
- Pure local mode — **your data never leaves your machine**, no cloud required

### 🎨 You Deserve a Beautiful Dashboard

<p align="center">
  <b>Web console recommended</b> — richest features, best experience.<br>
  <img src="https://img.shields.io/badge/Dark/Light-One_Click_Toggle-3B82F6?style=flat-square">
  <img src="https://img.shields.io/badge/Responsive-Mobile/Tablet-10B981?style=flat-square">
  <img src="https://img.shields.io/badge/Zero_Deps-Pure_HTML/CSS/JS-F59E0B?style=flat-square">
</p>

| | Old Way | Codex Memory Sync |
|---|---|---|
| **Device Migration** | Manually find & copy hidden folders | One-click export → double-click import script |
| **Tool Migration** | Impossible — start from scratch | Select sessions → one-click injection |
| **Data Security** | Raw files, no protection | AES-256-GCM encryption |
| **Session Preview** | Open raw JSON in Notepad | Chat bubble timeline + collapsible thinking |
| **Project Organization** | Everything jumbled together | Grouped by working directory |
| **Auto Sync** | Doesn't exist | Background daemon with file watcher |
| **Interface** | CLI + Notepad | Web Dashboard + Desktop GUI |

<br>

---

## 🚀 Out-of-the-Box in Three Steps

```bash
# 1. Clone
git clone https://github.com/YMY0730/codex-memory-sync.git
cd codex-memory-sync

# 2. Install
pip install -e .

# 3. Launch Web Console (Recommended)
python web_server.py
```

Open **http://127.0.0.1:8899** in your browser. Complete your first cross-device migration in under three minutes.

| Launch Method | Command | Best For |
|---------------|---------|----------|
| **🌐 Web Console** | `python web_server.py` | **Recommended** · Full features · Remote access |
| 🖥️ Desktop GUI | `python cli.py gui` | Traditional desktop experience |
| ⌨️ CLI | `codex-memory bridge c2o --all` | Scripts / Automation |

<br>

---

## ⚡ Real-World Scenarios

> **Scenario 1: You've been building a project with Codex on your work desktop for a month.**
>
> → Export an encrypted ZIP, take it home, double-click `import.bat`. Your laptop's Codex instantly knows your project architecture.

> **Scenario 2: You want to try OpenCode after months on Codex.**
>
> → Web console → 🔄 Bridge tab → check the sessions to migrate → one click. All your conversation history — including thinking processes — appears in OpenCode.

> **Scenario 3: You have 5 OpenCode working directories and want to organize them.**
>
> → 💬 Sessions tab → 5 directories automatically grouped. Click any session, full chat timeline appears on the right. Select and export to Codex format in one click.

<br>

---

## 📄 License

MIT © YMY0730

<p align="center">
  <sub>Built with ❤️ for the AI coding community. Star this repo if it saves you time and tokens.</sub>
</p>
