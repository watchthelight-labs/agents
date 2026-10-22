"""Upload new/changed UTF-8 files to the private inbox over SSH. Never deletes data."""
import argparse
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import uuid

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument("directory", nargs="?", type=Path, default=Path.home() / "Documents/Memory-Inbox")
args = parser.parse_args()
inbox = args.directory.resolve(strict=True)
if not inbox.is_dir():
    raise SystemExit("Supply an inbox directory containing UTF-8 text files")
private = root / "private"
private.mkdir(exist_ok=True)
state_path = private / "inbox-sync.json"
state = json.loads(state_path.read_text()) if state_path.exists() else {}
key = "~/.ssh/memory-server.pem"
ssh = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15", "-i", key, "my-server"]
count = 0
for path in sorted(inbox.rglob("*")):
    if path.is_symlink() or not path.is_file() or path.suffix.lower() not in {".txt", ".md", ".json", ".jsonl", ".csv"}:
        continue
    if not path.resolve().is_relative_to(inbox):
        continue
    raw = path.read_bytes()
    raw.decode("utf-8")  # Reject binary/unsupported encoding before transfer.
    digest = hashlib.sha256(raw).hexdigest()
    state_key = str(path)
    if state.get(state_key) == digest:
        continue
    relative = path.relative_to(inbox).as_posix()
    if any(ord(c) < 32 for c in relative):
        raise ValueError("Control characters in a filename are not supported")
    # Each local inbox gets its own namespace, preventing collisions between folders.
    namespace = hashlib.sha256(str(inbox).encode()).hexdigest()[:12]
    destination = "/srv/memory-mcp/inbox/" + namespace + "/" + relative
    temporary = "/srv/memory-mcp/inbox/.upload-" + uuid.uuid4().hex + ".part"
    subprocess.run(ssh + ["mkdir -p -- " + shlex.quote(destination.rsplit("/", 1)[0])], check=True)
    subprocess.run(["scp", "-q", "-i", key, str(path), "my-server:" + temporary], check=True)
    if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
        raise RuntimeError("Source changed during upload; retry when writing is complete")
    subprocess.run(ssh + ["chmod 640 -- " + shlex.quote(temporary) + " && sudo -n chown memory-mcp:ubuntu -- " + shlex.quote(temporary) + " && mv -- " + shlex.quote(temporary) + " " + shlex.quote(destination)], check=True)
    state[state_key] = digest
    count += 1
    print("Uploaded:", relative)
    temp_state = state_path.with_suffix(".tmp")
    temp_state.write_text(json.dumps(state, indent=2), encoding="utf-8")
    temp_state.replace(state_path)
print(f"Uploaded {count} new/changed files. The server indexes the inbox every two minutes.")
