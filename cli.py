from __future__ import annotations

import json
import sys
import time
import webbrowser
from pathlib import Path

import click

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src import config
from src.cloud import (
    AuthError,
    CloudError,
    NetworkError,
    delete_files,
    download_file,
    find_file_key_by_filename,
    github_auth_poll,
    github_auth_start,
    list_cloud_versions,
    manbaout_login,
    test_connection,
    unregister_version,
)
from src.daemon import daemon_status, do_pull, do_push, do_sync, start_daemon, stop_daemon
from src.export_local import create_export_zip, discover_memories, discover_rules, discover_sessions
from src.importer import DecryptError, import_from_file, preview_encrypted
from src.metadata import SyncStatus, compare
from src.utils import format_size, format_time


@click.group()
@click.version_option(version="1.0.0")
def cli():
    """Codex Memory Sync - 跨设备 Codex 记忆同步工具"""
    pass


@cli.command()
@click.option("--backend", type=click.Choice(["github", "manbaout", "none"]), default="none", help="存储后端")
def init(backend):
    """初始化配置"""
    config.set_backend(backend)

    if backend == "none":
        click.echo("💻 本地模式")
        click.echo("无需配置云后端，可直接使用 `codex-memory export` 导出本地压缩包。\n")

    elif backend == "github":
        click.echo("🐙 GitHub 私有仓库模式")
        click.echo("需要 GitHub OAuth App 的 Client ID")
        click.echo("获取: GitHub Settings → Developer settings → OAuth Apps → New OAuth App")
        click.echo("Homepage/Callback URL 填 http://localhost 即可\n")

        client_id = click.prompt("Client ID")
        click.echo("🔑 正在获取授权码...")
        try:
            result = github_auth_start(client_id)
            click.echo(f"\n请在浏览器中输入验证码: {result['user_code']}")
            click.echo(f"或直接访问: {result['verification_url']}")
            webbrowser.open(result["verification_url"])

            with click.progressbar(length=60, label="等待授权") as bar:
                for _ in range(60):
                    time.sleep(result["interval"])
                    bar.update(1)
                    try:
                        poll = github_auth_poll(client_id, result["device_code"])
                        if poll["status"] == "authorized":
                            click.echo(f"\n✅ 授权成功 ({poll['user']['login']})")
                            break
                    except AuthError as e:
                        click.echo(f"\n❌ {e}")
                        sys.exit(1)
                    except Exception:
                        pass
                else:
                    click.echo("\n⚠️ 授权超时，请重试")
                    sys.exit(1)

        except AuthError as e:
            click.echo(f"❌ {e}", err=True)
            sys.exit(1)
        except NetworkError as e:
            click.echo(f"❌ 网络错误: {e}", err=True)
            sys.exit(1)

    elif backend == "manbaout":
        click.echo("☁️ ManbaOut 云盘模式")
        click.echo("⚠️ 数据默认保存 3 天，到期自动清理\n")

        server = click.prompt("服务器地址", default="https://manbaout.cn")
        username = click.prompt("用户名")
        password = click.prompt("密码", hide_input=True)

        config.set_config_value(server, "cloud", "server_url")
        click.echo("🔑 正在登录...")
        try:
            manbaout_login(username, password)
            click.echo("✅ 登录成功")
        except AuthError as e:
            click.echo(f"❌ {e}", err=True)
            sys.exit(1)
        except NetworkError as e:
            click.echo(f"❌ 网络错误: {e}", err=True)
            sys.exit(1)

    if backend != "none":
        enc_password = click.prompt("加密密码", hide_input=True, confirmation_prompt=True)
        config.update_security(enc_password)

    backend_labels = {"github": "🐙 GitHub", "manbaout": "☁️ ManbaOut", "none": "💻 本地模式"}
    click.echo(f"✅ 初始化完成！后端: {backend_labels.get(backend, backend)}")


@cli.command()
def push():
    """推送本地记忆到云端"""
    try:
        result = do_push()
        click.echo(f"✅ 推送成功: {json.dumps(result, ensure_ascii=False)}")
    except Exception as e:
        click.echo(f"❌ 推送失败: {e}", err=True)
        sys.exit(1)


@cli.command()
def pull():
    """从云端拉取最新记忆"""
    try:
        result = do_pull()
        click.echo(f"✅ 拉取成功: 恢复了 {len(result.get('restored_files', []))} 个文件")
        click.echo(f"   来源设备: {result.get('source_device', 'unknown')}")
        click.echo(f"   版本: v{result.get('version', 0)}")
    except DecryptError as e:
        click.echo(f"❌ 解密失败: {e}", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"❌ 拉取失败: {e}", err=True)
        sys.exit(1)


@cli.command()
def sync():
    """完整同步（先拉后推）"""
    try:
        result = do_sync()
        assert result is not None
        click.echo("✅ 完整同步完成")
    except Exception as e:
        click.echo(f"❌ 同步失败: {e}", err=True)
        sys.exit(1)


@cli.command()
def status():
    """查看同步状态"""
    try:
        versions = list_cloud_versions()
    except Exception:
        versions = []

    result = compare(versions)
    local = result["local"]
    cloud = result["cloud"]
    backend = config.get_backend()

    status_labels = {
        SyncStatus.SYNCED.value: "✅ 已同步",
        SyncStatus.LOCAL_AHEAD.value: "🟡 本地领先（待推送）",
        SyncStatus.CLOUD_AHEAD.value: "🔵 云端领先（可拉取）",
        SyncStatus.CONFLICT.value: "🔴 冲突（两边都有新版本）",
        SyncStatus.UNINITIALIZED.value: "⚪ 未初始化",
    }

    click.echo(f"后端: {'🐙 GitHub' if backend == 'github' else '☁️ ManbaOut'}")
    click.echo(f"状态: {status_labels.get(result['status'], result['status'])}")
    click.echo(f"本地: v{local['version']}  (设备: {local['device_id']})")
    click.echo(f"云端: v{cloud['latest_version']}  (设备: {cloud.get('latest_device', '-')})")
    click.echo(f"云端版本数: {cloud['total_versions']}")

    ds = daemon_status()
    if ds["running"]:
        click.echo(f"守护进程: 🟢 运行中 (PID: {ds.get('pid')})")
    else:
        click.echo("守护进程: 🔴 未运行")


@cli.group()
def cloud():
    """云端版本管理"""
    pass


@cloud.command("list")
def cloud_list():
    """列出云端所有版本"""
    try:
        versions = list_cloud_versions()
        if not versions:
            click.echo("云端暂无版本")
            return
        click.echo(f"{'版本':<6} {'时间':<22} {'设备':<18} {'大小':<10} {'到期':<10} {'Hash'}")
        click.echo("-" * 95)
        for v in versions:
            ver = v.get("version", "?")
            t = v.get("time", "")[:19]
            dev = v.get("device", "")[:16]
            size = format_size(v.get("size", 0))
            h = v.get("hash", "")[:12]
            exp = v.get("expires_at", "")
            exp = f"{format_time(exp)[:10]}" if exp else "永久"
            click.echo(f"v{ver:<5} {t:<22} {dev:<18} {size:<10} {exp:<10} {h}")
    except (CloudError, NetworkError) as e:
        click.echo(f"❌ {e}", err=True)
        sys.exit(1)


@cloud.command("download")
@click.argument("version", type=int)
def cloud_download(version):
    """下载指定版本到本地并解密"""
    versions = list_cloud_versions()
    target = None
    for v in versions:
        if v.get("version") == version:
            target = v
            break
    if not target:
        click.echo(f"❌ 未找到版本 v{version}", err=True)
        sys.exit(1)

    filename = target.get("filename", "")
    key = find_file_key_by_filename(filename)
    if not key:
        key = target.get("hash", "")
    if not key:
        click.echo(f"❌ 文件不存在: {filename}", err=True)
        sys.exit(1)

    click.echo(f"📥 正在下载 v{version}...")
    temp_dir = config.CONFIG_DIR / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    dest = temp_dir / filename
    try:
        download_file(key, dest)
        password = config.get_config_value("security", "encryption_password") or ""
        if not password:
            password = click.prompt("加密密码", hide_input=True)

        preview = preview_encrypted(dest.read_bytes(), password)
        click.echo(f"   版本: v{preview['version']}")
        click.echo(f"   来源: {preview['device']}")
        click.echo(f"   文件数: {preview['file_count']}")
        for fn, sz in preview["file_sizes"].items():
            click.echo(f"     - {fn} ({format_size(sz)})")

        if click.confirm("是否还原到本地记忆目录？"):
            result = import_from_file(dest, password, config.get_memory_path())
            click.echo(f"✅ 已还原 {len(result['restored_files'])} 个文件")
        dest.unlink(missing_ok=True)
    except DecryptError:
        click.echo("❌ 解密失败，密码不正确", err=True)
        sys.exit(1)
    except Exception as e:
        click.echo(f"❌ 下载失败: {e}", err=True)
        sys.exit(1)


@cloud.command("delete")
@click.argument("version", type=int)
def cloud_delete(version):
    """删除云端指定版本"""
    versions = list_cloud_versions()
    target = None
    for v in versions:
        if v.get("version") == version:
            target = v
            break
    if not target:
        click.echo(f"❌ 未找到版本 v{version}", err=True)
        sys.exit(1)

    filename = target.get("filename", "")
    key = find_file_key_by_filename(filename)
    keys = [key] if key else []

    if not click.confirm(f"确认删除云端 v{version}?"):
        return

    try:
        if keys:
            delete_files(keys)
        unregister_version(version)
        click.echo(f"✅ 已删除 v{version}")
    except Exception as e:
        click.echo(f"❌ 删除失败: {e}", err=True)
        sys.exit(1)


@cli.group()
def github():
    """GitHub 后端管理"""
    pass


@github.command("auth")
def github_auth():
    """GitHub OAuth 授权"""
    client_id = config.get_config_value("github", "client_id") or ""
    if not client_id:
        client_id = click.prompt("Client ID")
    click.echo("🔑 正在获取授权码...")
    try:
        result = github_auth_start(client_id)
        click.echo(f"\n请在浏览器中输入验证码: {result['user_code']}")
        click.echo(f"或直接访问: {result['verification_url']}")
        webbrowser.open(result["verification_url"])

        with click.progressbar(length=60, label="等待授权") as bar:
            for _ in range(60):
                time.sleep(result["interval"])
                bar.update(1)
                try:
                    poll = github_auth_poll(client_id, result["device_code"])
                    if poll["status"] == "authorized":
                        click.echo(f"\n✅ 授权成功 ({poll['user']['login']})")
                        return
                except AuthError as e:
                    click.echo(f"\n❌ {e}")
                    sys.exit(1)
                except Exception:
                    pass
        click.echo("\n⚠️ 授权超时")
    except (AuthError, NetworkError) as e:
        click.echo(f"❌ {e}", err=True)
        sys.exit(1)


@github.command("status")
def github_status():
    """查看 GitHub 授权状态"""
    token = config.get_config_value("github", "token") or ""
    owner = config.get_config_value("github", "owner") or ""
    if not token:
        click.echo("⚪ 未授权")
    else:
        try:
            test_connection()
            click.echo(f"✅ 已授权 (用户: {owner})")
        except Exception:
            click.echo("🔴 Token 无效")


@github.command("revoke")
def github_revoke():
    """吊销 GitHub 授权"""
    if click.confirm("确认吊销 GitHub 授权？"):
        config.update_github_config(token="", owner="")
        click.echo("✅ 已吊销")


@cli.group()
def manbaout():
    """ManbaOut 后端管理"""
    pass


@manbaout.command("expiry")
@click.argument("days", type=int)
def manbaout_expiry(days):
    """设置 ManbaOut 数据保存期限（天）"""
    if days < 1 or days > 365:
        click.echo("❌ 请输入 1 ~ 365 之间的数字", err=True)
        sys.exit(1)
    config.update_manbaout_expiry(days)
    click.echo(f"✅ 保存期限已设为 {days} 天")


@cli.group()
def local():
    """本地记忆管理"""
    pass


@local.command("list")
def local_list():
    """列出本地记忆文件"""
    memory_path = config.get_memory_path()
    selected = set(config.get_config_value("local", "selected_files") or [])

    if not memory_path.exists():
        click.echo(f"记忆目录不存在: {memory_path}")
        return

    files = sorted(memory_path.iterdir(), key=lambda p: (p.is_dir(), p.name.lower()))
    click.echo(f"本地记忆: {memory_path}")
    click.echo(f"{'选中':<4} {'文件名':<40} {'大小':<10} {'修改时间'}")
    click.echo("-" * 80)
    for f in files:
        if f.name.startswith("."):
            continue
        sel = "☑" if f.name in selected else "☐"
        if f.is_dir():
            click.echo(f"{sel:<4} {f.name + '/':<40} {'-':<10} {format_time(str(f.stat().st_mtime))}")
        else:
            click.echo(
                f"{sel:<4} {f.name:<40} {format_size(f.stat().st_size):<10} {format_time(str(f.stat().st_mtime))}"
            )


@local.command("tree")
def local_tree():
    """树形展示全部本地数据（记忆+会话+规则）"""
    codex_dir = Path.home() / ".codex"
    memories = discover_memories(codex_dir / "memories")
    sessions_idx, sessions_un = discover_sessions(codex_dir / "sessions", codex_dir / "session_index.jsonl")
    rules = discover_rules(codex_dir / "rules")

    click.echo("📁 ~/.codex/")
    click.echo(f"  📁 记忆文件/ ({len(memories)} 项)")
    for item in memories:
        if item.get("is_dir"):
            click.echo(f"    📁 {item['name']}")
            for c in item.get("children", []):
                click.echo(f"      📄 {c['name']} ({format_size(c['size'])})")
        else:
            click.echo(f"    📄 {item['name']} ({format_size(item['size'])})")

    total_sessions = len(sessions_idx) + len(sessions_un)
    if total_sessions:
        total_size = sum(s["size"] for s in sessions_idx) + sum(p.stat().st_size for p in sessions_un)
        click.echo(f"  📁 会话记录/ ({total_sessions} 个, {format_size(total_size)})")
        for s in sessions_idx:
            size_warn = " ⚠️ 较大" if s["size"] > 10 * 1024 * 1024 else ""
            click.echo(f"    ☐ {s['thread_name']} ({format_size(s['size'])}{size_warn})")
        if sessions_un:
            click.echo(f"    📁 未索引会话/ ({len(sessions_un)} 个)")
            for p in sessions_un:
                click.echo(f"      📄 {p.parent.name}/{p.name} ({format_size(p.stat().st_size)})")

    if rules:
        click.echo(f"  📁 规则文件/ ({len(rules)} 项)")
        for r in rules:
            click.echo(f"    📄 {r['name']} ({format_size(r['size'])})")


@cli.command()
@click.option("-o", "--output", default=None, help="输出文件路径 (默认: 当前目录/codex-context-{version}.zip)")
@click.option("--memories/--no-memories", default=True, help="包含记忆文件")
@click.option("--sessions/--no-sessions", default=False, help="包含会话记录")
@click.option("--rules/--no-rules", default=False, help="包含规则文件")
def export(output, memories, sessions, rules):
    """导出本地数据为可迁移的 ZIP 压缩包"""
    codex_dir = Path.home() / ".codex"

    memory_files: list[Path] = []
    session_files: list[Path] = []
    rule_files: list[Path] = []

    if memories:
        mem_items = discover_memories(codex_dir / "memories")
        for item in mem_items:
            if item.get("is_dir"):
                for c in item.get("children", []):
                    memory_files.append(c["path"])
            else:
                memory_files.append(item["path"])

    if sessions:
        sess_idx, sess_un = discover_sessions(codex_dir / "sessions", codex_dir / "session_index.jsonl")
        for s in sess_idx:
            session_files.append(s["path"])
        for p in sess_un:
            session_files.append(p)

    if rules:
        rule_items = discover_rules(codex_dir / "rules")
        for r in rule_items:
            rule_files.append(r["path"])

    total = sum(f.stat().st_size for f in memory_files + session_files + rule_files)
    total_count = len(memory_files) + len(session_files) + len(rule_files)

    if total_count == 0:
        click.echo("⚠️ 没有可导出的文件", err=True)
        return

    if not output:
        ver = config.get_config_value("metadata", "local_version") or 1
        output = f"codex-context-v{ver}.zip"

    click.echo(f"📦 准备导出 {total_count} 个文件 ({format_size(total)})")

    if sessions and total > 50 * 1024 * 1024:
        click.echo(f"⚠️ 包含会话记录，总大小 {format_size(total)}，可能较大")
        if not click.confirm("确认导出？"):
            return

    try:
        path = create_export_zip(
            Path(output),
            memory_files,
            session_files,
            rule_files,
            codex_dir / "memories",
            codex_dir / "sessions",
            codex_dir / "rules",
        )
        click.echo(f"✅ 导出成功: {path} ({format_size(path.stat().st_size)})")
        click.echo(f"   内容: {len(memory_files)} 记忆 + {len(session_files)} 会话 + {len(rule_files)} 规则")
        click.echo("   解压后双击 import.sh 即可一键导入")
    except Exception as e:
        click.echo(f"❌ 导出失败: {e}", err=True)
        sys.exit(1)


@cli.group()
def daemon():
    """守护进程管理"""
    pass


@daemon.command("start")
def daemon_start():
    """启动守护进程（后台自动同步）"""
    start_daemon()


@daemon.command("stop")
def daemon_stop():
    """停止守护进程"""
    stop_daemon()
    click.echo("守护进程已停止")


@daemon.command("status")
def daemon_status_cmd():
    """查看守护进程状态"""
    ds = daemon_status()
    if ds["running"]:
        click.echo("🟢 守护进程运行中")
        click.echo(f"   PID: {ds.get('pid')}")
    else:
        click.echo("🔴 守护进程未运行")


@cli.command()
def gui():
    """启动图形界面"""
    config.ensure_config_dir()
    try:
        from gui.app_modern import main

        main()
    except ImportError:
        try:
            from gui.app import main

            main()
        except ImportError as e:
            click.echo(f"❌ 无法启动 GUI: {e}", err=True)
            click.echo("请确保 tkinter 已安装", err=True)
            sys.exit(1)


@cli.command()
def test():
    """测试连接"""
    backend = config.get_backend()

    if backend == "none":
        click.echo("💻 本地模式")
        click.echo("无需配置云后端，可直接使用 `codex-memory export` 导出本地压缩包。")
        return

    try:
        info = test_connection()
        if backend == "github":
            click.echo("✅ GitHub 连接成功")
            click.echo(f"   用户: {info.get('login', '?')}")
        else:
            click.echo("✅ ManbaOut 连接成功")
            click.echo(f"   用户: {info.get('username', '?')}")
    except (AuthError, NetworkError, CloudError) as e:
        click.echo(f"❌ 连接失败: {e}", err=True)
        sys.exit(1)


# ══════════════════════════════════════════════════════════════════════════════
# 跨工具桥接命令
# ══════════════════════════════════════════════════════════════════════════════


@cli.group()
def bridge():
    """Codex ↔ OpenCode 跨工具同步"""
    pass


@bridge.command("c2o")
@click.option("--all", "-a", "all_sessions", is_flag=True, help="导入全部已索引会话")
@click.option("--agents", "sync_agents", is_flag=True, help="同步 AGENTS.md")
@click.option("--skills", "sync_skills_flag", is_flag=True, help="同步 Skills")
@click.option("--memories", "sync_memories", is_flag=True, help="同步记忆文件到 OpenCode")
@click.option("--dry-run", is_flag=True, help="预览模式")
def bridge_c2o(all_sessions, sync_agents, sync_skills_flag, sync_memories, dry_run):
    """Codex → OpenCode 导入"""
    from src.bridge import (
        codex_all_to_opencode,
        sync_agents_md,
        sync_memories_to_opencode,
        sync_skills,
    )
    from src.export_local import discover_sessions

    if sync_agents:
        r = sync_agents_md("c2o")
        click.echo(f"📄 AGENTS.md: {r.get('action', r.get('error', '?'))}")
    if sync_skills_flag:
        for r in sync_skills("c2o"):
            click.echo(f"📁 Skills/{r.get('name', '?')}: {r.get('action', r.get('error', '?'))}")
    if sync_memories:
        r = sync_memories_to_opencode()
        click.echo(f"🧠 记忆: {r.get('files', 0)} 个已追加到 OpenCode AGENTS.md")

    if all_sessions:
        sessions_dir = Path.home() / ".codex" / "sessions"
        index_path = Path.home() / ".codex" / "session_index.jsonl"
        indexed, _ = discover_sessions(sessions_dir, index_path)
        if dry_run:
            click.echo(f"🔍 预览: {len(indexed)} 个会话可导入")
            for i, s in enumerate(indexed, 1):
                click.echo(f"  [{i}] {s.get('thread_name', s['name'])}")
        else:
            for _s in indexed:
                r = codex_all_to_opencode(dry_run=False)
                for item in r:
                    status = "✅" if item.get("ok") else "❌"
                    click.echo(f"  {status} {item.get('title', '?')}: {item.get('message_count', 0)} 条")

    if not any([all_sessions, sync_agents, sync_skills_flag, sync_memories]):
        click.echo("用法: codex-memory bridge c2o --all --agents --skills --memories")


@bridge.command("o2c")
@click.option("--all", "-a", "all_sessions", is_flag=True, help="导出全部会话")
@click.option("--agents", "sync_agents", is_flag=True, help="同步 AGENTS.md")
@click.option("--skills", "sync_skills_flag", is_flag=True, help="同步 Skills")
@click.option("--dry-run", is_flag=True, help="预览模式")
def bridge_o2c(all_sessions, sync_agents, sync_skills_flag, dry_run):
    """OpenCode → Codex 导出"""
    from src.bridge import opencode_to_codex, read_opencode_db, sync_agents_md, sync_skills

    data = read_opencode_db()
    sessions = data.get("sessions", [])
    click.echo(f"OpenCode: {len(sessions)} 个会话")

    if sync_agents:
        r = sync_agents_md("o2c")
        click.echo(f"📄 AGENTS.md: {r.get('action', r.get('error', '?'))}")
    if sync_skills_flag:
        for r in sync_skills("o2c"):
            click.echo(f"📁 Skills: {r.get('name', '?')} {r.get('action', '?')}")
    if all_sessions:
        for r in opencode_to_codex(dry_run=dry_run):
            click.echo(f"  ✅ {r.get('title')} → {r.get('lines')} 行")
    if not any([all_sessions, sync_agents, sync_skills_flag]):
        for i, s in enumerate(sessions, 1):
            click.echo(f"  [{i}] {s.get('title', s['id'][:12])} ({len(s.get('messages', []))} 条)")


@bridge.command("list")
def bridge_list():
    """列出可同步的会话"""
    from src.bridge import _codex_sessions_dir, read_opencode_db
    from src.export_local import discover_sessions

    click.echo("🧠 Codex:")
    sd = _codex_sessions_dir()
    if sd:
        idx, unidx = discover_sessions(sd, sd.parent / "session_index.jsonl")
        for i, s in enumerate(idx, 1):
            click.echo(f"  [{i}] {s.get('thread_name', s['name'])} ({format_size(s['size'])})")
        if unidx:
            click.echo(f"  +{len(unidx)} 个未索引")
    data = read_opencode_db()
    if data.get("sessions"):
        click.echo(f"\n💬 OpenCode ({len(data['sessions'])} 个):")
        for i, s in enumerate(data["sessions"], 1):
            click.echo(f"  [{i}] {s.get('title', s['id'][:12])} ({len(s.get('messages', []))} 条)")


if __name__ == "__main__":
    cli()
