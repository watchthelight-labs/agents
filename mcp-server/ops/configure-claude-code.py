"""Use Claude's CLI to register the authenticated server without echoing its token."""
import json
from pathlib import Path
import shutil
import subprocess

root = Path(__file__).resolve().parents[1]
connection = json.loads((root / "private/connection.json").read_text(encoding="utf-8"))
config = Path.home() / ".claude.json"
current = json.loads(config.read_text(encoding="utf-8")) if config.exists() else {}
existing = current.get("mcpServers", {}).get("bash-memory")
expected = {"type": "http", "url": connection["url"], "headers": {"Authorization": "Bearer " + connection["token"]}}
if existing is not None:
    if existing != expected:
        raise RuntimeError("A different bash-memory connector already exists; refusing to overwrite")
    print("Claude Code connector is already configured.")
else:
    backup = root / "private/claude-config-before.json"
    if config.exists() and not backup.exists():
        shutil.copy2(config, backup)
    executable = shutil.which("claude.cmd") or shutil.which("claude")
    result = subprocess.run([executable, "mcp", "add", "--transport", "http", "--scope", "user", "bash-memory", connection["url"], "--header", "Authorization: Bearer " + connection["token"]], capture_output=True, text=True, timeout=30)
    if result.returncode:
        raise RuntimeError(result.stderr.replace(connection["token"], "[REDACTED]"))
    updated = json.loads(config.read_text(encoding="utf-8"))
    assert updated["mcpServers"]["bash-memory"] == expected
    print("Claude Code: bash-memory registered in user scope. Other connectors preserved.")
