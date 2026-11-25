"""一次跑完所有自動化測試（後端 pytest + 前端 node）。

用法（在專案根目錄）：  python tests/run_all.py
commit 前請先跑一次；原有的語法檢查（node --check）仍然要做，兩者互補。
"""
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run(label, cmd):
    print(f"\n=== {label} ===", flush=True)
    return subprocess.run(cmd, cwd=ROOT).returncode == 0


def main():
    ok = run("後端（pytest）", [sys.executable, "-m", "pytest", "tests", "-q"])
    if shutil.which("node"):
        ok = run("前端（node）", ["node", "--test", "tests/frontend_helpers.test.js"]) and ok
    else:
        print("\n找不到 node，略過前端測試")
        ok = False
    print("\n全部通過" if ok else "\n有測試失敗")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
