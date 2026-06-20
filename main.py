"""
Huginn 遗留入口 v4 — 已弃用
用法：
    python main.py <你的数据文件.csv|xlsx>

此入口已不再维护。请使用新的主入口：
    python -m huginn.cli.runner <文件路径> <分析需求>
"""
import sys
import subprocess
from pathlib import Path


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    script = Path(__file__).parent / "huginn" / "cli" / "runner.py"
    subprocess.run([sys.executable, str(script), sys.argv[1]] + sys.argv[2:], check=False)


if __name__ == "__main__":
    main()
