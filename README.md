# Codex Memory Sync

跨设备 Codex 记忆同步工具 —— 在多个设备间安全传输 Codex AI 助手的记忆、会话和规则文件，**省 token、提高缓存命中、省钱且准确**。

## 功能

- **加密同步** — AES-256-GCM 端到端加密，密码从不出你的设备
- **双后端** — 支持 GitHub 私有仓库和 ManbaOut.cn 云盘
- **后台守护进程** — 文件监视 + 定时拉取，自动保持同步
- **本地导出** — 纯 ZIP 导出，双击 import.sh / import.bat 一键导入
- **版本管理** — 多版本存储，冲突检测，按需回退
- **GUI + CLI** — Tkinter 图形界面 或 Click 命令行

## 安装

```bash
pip install codex-memory-sync
```

或者从源码安装：

```bash
pip install -e .
```

### 依赖

- Python >= 3.9
- `click`, `requests`, `cryptography`, `watchdog`, `Pillow`, `pystray`

## 快速开始

### CLI

```bash
# 初始化（选择后端并配置）
codex-memory init

# 查看状态
codex-memory status

# 推送本地记忆到云端
codex-memory push

# 从云端拉取最新记忆
codex-memory pull

# 完整同步（先拉后推）
codex-memory sync

# 导出本地记忆为 ZIP（可离线传输）
codex-memory export
```

### GUI

```bash
codex-memory gui
```

或直接运行 `python gui_app.py`。

### 守护进程（后台自动同步）

```bash
codex-memory daemon start
codex-memory daemon stop
codex-memory daemon status
```

## 云后端说明

| 后端 | 存储位置 | 有效期 | 认证方式 |
|------|----------|--------|----------|
| GitHub | 你的私有仓库 | 永久 | OAuth Device Flow |
| ManbaOut | manbaout.cn | 默认 3 天 | 用户名/密码 |

### GitHub 配置

1. 创建 GitHub OAuth App: Settings → Developer settings → OAuth Apps
2. Homepage/Callback URL 填 `http://localhost`
3. 获取 Client ID，运行 `codex-memory init --backend github`

### ManbaOut 配置

```bash
codex-memory init --backend manbaout
```

## 文件结构

```
~/.codex-memory-sync/config.json    # 配置文件
~/.codex/memories/                  # Codex 记忆文件
~/.codex/sessions/                  # 会话上下文记录
~/.codex/rules/                     # 规则文件
```

## 安全警告

⚠️ **加密密码以明文形式存储在 `~/.codex-memory-sync/config.json` 中。**

这是为了让守护进程能够在无人值守时自动运行。请确保配置文件权限为 600，并仅在受信任的设备上使用。未来版本计划集成系统密钥链（macOS Keychain / Windows Credential Manager）。

## 开发

```bash
# 安装开发依赖
pip install ruff pyright

# 代码检查
ruff check .
ruff format --check .

# 类型检查
pyright
```

## License

MIT
