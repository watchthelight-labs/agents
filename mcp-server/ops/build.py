"""Package the application for install.sh: private/app.tar.gz with code, ops files and the built dashboard."""
from pathlib import Path
import subprocess
import shutil
import sys
import tarfile

with_ui = "--no-ui" not in sys.argv
root = Path(__file__).resolve().parents[1]
ui = root / "dash-ui"
if with_ui and (ui / "package.json").exists():
    npm = shutil.which("npm.cmd") or shutil.which("npm")
    subprocess.run([npm, "ci"], cwd=ui, check=True)
    subprocess.run([npm, "run", "build"], cwd=ui, check=True)

SKIP = {"__pycache__", ".pytest_cache", "node_modules"}


def keep(info):
    parts = Path(info.name).parts
    if SKIP & set(parts) or info.name.endswith((".pyc", ".egg-info")):
        return None
    info.uid = info.gid = 0
    info.uname = info.gname = "root"
    return info


out = root / "private" / "app.tar.gz"
out.parent.mkdir(exist_ok=True)
with tarfile.open(out, "w:gz") as tar:
    for name in ("src", "ops", "pyproject.toml", "requirements.lock", "README.md"):
        tar.add(root / name, arcname=name, filter=keep)
    if with_ui and (ui / "dist" / "index.html").exists():
        tar.add(ui / "dist", arcname="dash-ui/dist", filter=keep)
print(f"Built {out.relative_to(root)} ({out.stat().st_size // 1024} KiB)")
