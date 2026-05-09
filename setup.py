from setuptools import find_packages, setup

setup(
    name="codex-memory-sync",
    version="1.0.0",
    description="跨设备 Codex 记忆同步工具",
    author="Codex Memory Sync",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "click>=8.0.0",
        "requests>=2.28.0",
        "cryptography>=41.0.0",
        "watchdog>=3.0.0",
        "Pillow>=9.0.0",
        "pystray>=0.19.0",
    ],
    entry_points={
        "console_scripts": [
            "codex-memory=cli:cli",
        ],
    },
    python_requires=">=3.9",
)
