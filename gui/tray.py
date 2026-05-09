_tray_icon = None


def setup_tray(app):
    global _tray_icon
    try:
        import pystray
        from PIL import Image, ImageDraw

        def _create_icon():
            img = Image.new("RGB", (64, 64), "#4a90d9")
            draw = ImageDraw.Draw(img)
            draw.rectangle([16, 16, 48, 48], fill="white")
            draw.text((24, 20), "CX", fill="#4a90d9")
            return img

        def _on_show(icon, item):
            app.deiconify()
            app.lift()

        def _on_push(icon, item):
            from src.daemon import do_push

            app.after(0, lambda: do_push())

        def _on_pull(icon, item):
            from src.daemon import do_pull

            app.after(0, lambda: do_pull())

        def _on_quit(icon, item):
            icon.stop()
            app.destroy()

        menu = pystray.Menu(
            pystray.MenuItem("打开主面板", _on_show, default=True),
            pystray.MenuItem("📤 立即推送", _on_push),
            pystray.MenuItem("📥 立即拉取", _on_pull),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("退出", _on_quit),
        )

        _tray_icon = pystray.Icon("codex_memory_sync", _create_icon(), "Codex Memory Sync", menu)
        return _tray_icon
    except ImportError:
        return None


def has_tray_support() -> bool:
    import importlib.util

    return importlib.util.find_spec("pystray") is not None
